"""Costing the same driving as if a different car had done it.

Symmetric by design. The car you drive and the car you are curious about can
each be any fuel, so this works for an EV owner asking what petrol would have
cost, and equally for a diesel owner asking what an EV would have saved.

Each stretch of driving is priced at the rate that applied *at the time*, never
today's. Pricing a year of history at this week's rate would be wrong in
whichever direction fuel or electricity has moved since, and getting that right
is the entire reason the price series and tariff versions are stored.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.fuel_price import FuelKind
from app.models.vehicle import FuelType, Vehicle
from app.services import emissions, fuel_pricing, tariffs

# Which pump price a car actually buys. A hybrid burns petrol unless it is
# specifically a diesel one, which the fuel type does not distinguish.
FUEL_KIND = {
    FuelType.petrol: FuelKind.petrol_95,
    FuelType.diesel: FuelKind.diesel,
    FuelType.hybrid: FuelKind.petrol_95,
}


class CannotCompare(ValueError):
    """The comparison car lacks the one figure the whole estimate rests on."""


@dataclass
class PricedInterval:
    start_date: str
    end_date: str
    distance_km: float
    quantity: float
    unit_price: float | None
    cost: float | None
    price_as_of: str | None
    price_is_estimate: bool


@dataclass
class Comparison:
    distance_km: float
    actual_cost: float
    alternative_cost: float
    # Positive means the alternative would have cost more — i.e. you are ahead.
    saving: float
    actual_cost_per_100km: float | None
    alternative_cost_per_100km: float | None

    # Burning the fuel and generating the electricity, not the full lifecycle.
    actual_co2_kg: float | None
    alternative_co2_kg: float
    # Positive means the alternative would have emitted more.
    co2_saving_kg: float
    actual_co2_g_per_km: float | None
    alternative_co2_g_per_km: float | None
    grid_co2_g_per_kwh: float

    # What each car is quoted to use, exactly as entered. Both sides of the
    # comparison come from these, so two cars with the same figure compare
    # identically no matter which one is being driven.
    #
    # Your car is the one with a second opinion available, since it is the one
    # with a log behind it. `measured_weight` says how far the figure used
    # slides from what you entered towards what you actually achieved.
    your_basis: float
    your_basis_quoted: float
    your_basis_measured: float | None
    measured_weight: float
    basis: float
    basis_label: str

    # What you actually spent, kept separate: it is real money rather than
    # part of the like-for-like sum.
    actual_spend: float
    your_quantity: float
    quantity: float
    unit: str
    unit_label: str

    comparison_vehicle: str
    comparison_fuel: FuelType
    unpriced_intervals: int
    used_fallback_price: bool
    intervals: list[PricedInterval]


def quoted_consumption(vehicle: Vehicle) -> tuple[float | None, str, str, str]:
    """The car's published figure per 100 km, and how to describe it.

    Returns (rate or None, unit, unit label, basis label).
    """
    if vehicle.fuel_type == FuelType.electric:
        rate = vehicle.consumption_kwh_per_100km
        if not rate and vehicle.battery_capacity_kwh and vehicle.wltp_range_km:
            # Derivable from the spec: a full battery over its rated range.
            rate = vehicle.battery_capacity_kwh / vehicle.wltp_range_km * 100
        return (round(rate, 2) if rate else None), "kwh", "kWh", "kWh/100km"

    return vehicle.fuel_consumption_l_per_100km, "litres", "L", "L/100km"


def consumption_of(vehicle: Vehicle) -> tuple[float, str, str, str]:
    """As above, but insisting on a figure — the estimate rests entirely on it."""
    rate, unit, unit_label, basis_label = quoted_consumption(vehicle)
    if not rate:
        raise CannotCompare(
            f"{vehicle.make} {vehicle.model} needs a consumption figure ({basis_label})"
            + (
                ", or a battery size and range to derive one from"
                if vehicle.fuel_type == FuelType.electric
                else ""
            )
        )
    return rate, unit, unit_label, basis_label


def _price_electric(
    db: Session, user_id: int, day: datetime.date, fallback: float | None
) -> tuple[float | None, str | None, bool]:
    """A per-kWh price for a hypothetical EV on a given date.

    Uses the tariff version in force then, taking its cheapest band: a car you
    do not own has no charging history to say when it would have been plugged
    in, and someone weighing up an EV would charge at home overnight. It is
    reported as an estimate either way.
    """
    found = tariffs.rate_for(db, user_id, day, at=None)
    if found:
        tariff, rate = found
        return rate.price_per_kwh, tariff.effective_from.isoformat(), True
    return fallback, None, True


def _price_liquid(
    db: Session, day: datetime.date, region: str, kind: FuelKind,
    country: str, fallback: float | None,
) -> tuple[float | None, str | None, bool]:
    quote = fuel_pricing.price_on(db, day, country=country, region=region, fuel_kind=kind)
    if quote:
        return quote.price_per_litre, quote.as_of.isoformat(), quote.is_estimate
    return fallback, None, True


def _price_basis(vehicle: Vehicle) -> str:
    """What this car buys, so two cars can be recognised as buying the same
    thing. A hybrid buys petrol; its electricity is priced separately."""
    if vehicle.fuel_type == FuelType.electric:
        return "electricity"
    return FUEL_KIND.get(vehicle.fuel_type, FuelKind.petrol_95).value


def _paid_unit_price(iv) -> float | None:
    """What you actually paid per litre or kWh over this interval.

    Taken from the fill that closed it — cost divided by what went in. This is
    the truest price available: it is the receipt, not a national average, and
    it already reflects where and when you filled up.
    """
    added = (getattr(iv, "volume_added_litres", None) or 0) + (
        getattr(iv, "energy_added_kwh", None) or 0
    )
    if not added or iv.cost is None:
        return None
    # A plug-in hybrid buys two things on one receipt, so the split is unknown.
    if (getattr(iv, "volume_added_litres", None) or 0) and (
        getattr(iv, "energy_added_kwh", None) or 0
    ):
        return None
    return iv.cost / added


def blend(quoted: float, measured: float | None, weight: float) -> float:
    """Slide between the figure entered for a car and the one it achieved.

    Nothing is inferred here — the weight is chosen deliberately, and 0 keeps
    the comparison strictly like-for-like. At anything above 0 your car is
    judged on your roads while the other is still on its published figure, so
    the two stop being directly comparable; that is a reasonable thing to want,
    but the interface has to say it rather than arrange it quietly.
    """
    if measured is None or weight <= 0:
        return quoted
    weight = min(weight, 1.0)
    return round(quoted * (1 - weight) + measured * weight, 2)


def compare(
    db: Session,
    user_id: int,
    intervals: list,
    comparison_vehicle: Vehicle,
    driven_vehicle: Vehicle,
    measured_consumption: float | None = None,
    measured_weight: float = 0.0,
    country: str = "IE",
    fallback_price_per_litre: float | None = None,
    fallback_price_per_kwh: float | None = None,
) -> Comparison:
    """Price the same driving in two cars, on equal terms.

    Both sides use the consumption figure entered for that car, and the same
    unit price wherever the fuels match. Nothing is scaled or inferred: two
    cars quoted at the same figure come out identical, which is the only way
    the answer can be read as being about the cars rather than about how the
    numbers were arrived at.
    """
    your_quoted, your_unit, your_unit_label, _ = consumption_of(driven_vehicle)
    their_rate, unit, unit_label, basis_label = consumption_of(comparison_vehicle)
    your_rate = blend(your_quoted, measured_consumption, measured_weight)

    # Same *fuel*, not merely the same unit: petrol and diesel are both litres
    # but are bought at different pumps, and have diverged by 20c before now.
    same_fuel = _price_basis(driven_vehicle) == _price_basis(comparison_vehicle)
    electric = comparison_vehicle.fuel_type == FuelType.electric
    fallback = fallback_price_per_kwh if electric else fallback_price_per_litre
    kind = FUEL_KIND.get(comparison_vehicle.fuel_type, FuelKind.petrol_95)

    priced: list[PricedInterval] = []
    your_total = their_total = 0.0
    your_quantity = their_quantity = 0.0
    used_fallback = False

    for iv in intervals:
        day = datetime.date.fromisoformat(iv.end_date)
        yours = iv.distance_km / 100.0 * your_rate
        theirs = iv.distance_km / 100.0 * their_rate
        your_quantity += yours
        their_quantity += theirs

        # What you paid is the best price there is, so it is used for your car
        # and — when the other runs on the same fuel — for that one too.
        paid = _paid_unit_price(iv)

        if paid is not None and same_fuel:
            unit_price, as_of, is_estimate = paid, iv.end_date, False
        elif electric:
            unit_price, as_of, is_estimate = _price_electric(db, user_id, day, fallback)
        else:
            unit_price, as_of, is_estimate = _price_liquid(
                db, day, iv.location_city or "", kind, country, fallback
            )

        your_price = paid if paid is not None else (unit_price if same_fuel else None)
        if as_of is None and unit_price is not None:
            used_fallback = True

        their_cost = round(theirs * unit_price, 2) if unit_price is not None else None
        if their_cost is not None:
            their_total += their_cost
        if your_price is not None:
            your_total += yours * your_price

        priced.append(
            PricedInterval(
                start_date=iv.start_date,
                end_date=iv.end_date,
                distance_km=iv.distance_km,
                quantity=round(theirs, 2),
                unit_price=unit_price,
                cost=their_cost,
                price_as_of=as_of,
                price_is_estimate=is_estimate,
            )
        )

    their_co2 = (
        emissions.from_kwh(their_quantity)
        if electric
        else emissions.from_litres(their_quantity, comparison_vehicle.fuel_type)
    )
    your_co2 = (
        emissions.from_kwh(your_quantity)
        if driven_vehicle.fuel_type == FuelType.electric
        else emissions.from_litres(your_quantity, driven_vehicle.fuel_type)
    )

    distance = round(sum(i.distance_km for i in intervals), 2)
    # Real money, from the receipts. Only intervals count: the first fill paid
    # for driving that predates the log and has no distance here to sit against.
    spend = round(sum(i.cost or 0 for i in intervals), 2)
    yours_modelled = round(your_total, 2)
    theirs_modelled = round(their_total, 2)

    return Comparison(
        distance_km=distance,
        actual_cost=yours_modelled,
        alternative_cost=theirs_modelled,
        saving=round(theirs_modelled - yours_modelled, 2),
        actual_cost_per_100km=(
            round(yours_modelled / distance * 100, 2) if distance else None
        ),
        alternative_cost_per_100km=(
            round(theirs_modelled / distance * 100, 2) if distance else None
        ),
        actual_co2_kg=round(your_co2 / 1000, 2) if your_co2 else None,
        alternative_co2_kg=round(their_co2 / 1000, 2),
        co2_saving_kg=round((their_co2 - your_co2) / 1000, 2),
        actual_co2_g_per_km=round(your_co2 / distance, 1) if distance and your_co2 else None,
        alternative_co2_g_per_km=(
            round(their_co2 / distance, 1) if distance and their_co2 else None
        ),
        grid_co2_g_per_kwh=emissions.grid_intensity(),
        your_basis=your_rate,
        your_basis_quoted=your_quoted,
        your_basis_measured=(
            round(measured_consumption, 2) if measured_consumption else None
        ),
        measured_weight=(
            round(min(measured_weight, 1.0), 2) if measured_consumption else 0.0
        ),
        basis=their_rate,
        basis_label=basis_label,
        actual_spend=spend,
        your_quantity=round(your_quantity, 2),
        quantity=round(their_quantity, 2),
        unit=unit,
        unit_label=unit_label,
        comparison_vehicle=f"{comparison_vehicle.make} {comparison_vehicle.model}",
        comparison_fuel=comparison_vehicle.fuel_type,
        unpriced_intervals=sum(1 for p in priced if p.cost is None),
        used_fallback_price=used_fallback,
        intervals=priced,
    )
