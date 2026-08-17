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

    quantity: float
    unit: str
    unit_label: str
    basis: float
    basis_label: str

    comparison_vehicle: str
    comparison_fuel: FuelType
    unpriced_intervals: int
    used_fallback_price: bool
    intervals: list[PricedInterval]


def consumption_of(vehicle: Vehicle) -> tuple[float, str, str, str]:
    """What the car uses per 100 km, and how to describe it.

    Returns (rate, unit, unit label, basis label).
    """
    if vehicle.fuel_type == FuelType.electric:
        rate = vehicle.consumption_kwh_per_100km
        if not rate and vehicle.battery_capacity_kwh and vehicle.wltp_range_km:
            # Derivable from the spec: a full battery over its rated range.
            rate = vehicle.battery_capacity_kwh / vehicle.wltp_range_km * 100
        if not rate:
            raise CannotCompare(
                f"{vehicle.make} {vehicle.model} needs a consumption figure "
                "(kWh/100km), or a battery size and range to derive one from"
            )
        return round(rate, 2), "kwh", "kWh", "kWh/100km"

    rate = vehicle.fuel_consumption_l_per_100km
    if not rate:
        raise CannotCompare(
            f"{vehicle.make} {vehicle.model} needs a fuel consumption figure (L/100km)"
        )
    return rate, "litres", "L", "L/100km"


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


def compare(
    db: Session,
    user_id: int,
    intervals: list,
    comparison_vehicle: Vehicle,
    country: str = "IE",
    fallback_price_per_litre: float | None = None,
    fallback_price_per_kwh: float | None = None,
) -> Comparison:
    """Price `intervals` as though `comparison_vehicle` had driven them."""
    rate, unit, unit_label, basis_label = consumption_of(comparison_vehicle)
    electric = comparison_vehicle.fuel_type == FuelType.electric
    fallback = fallback_price_per_kwh if electric else fallback_price_per_litre
    kind = FUEL_KIND.get(comparison_vehicle.fuel_type, FuelKind.petrol_95)

    priced: list[PricedInterval] = []
    total = 0.0
    used_fallback = False

    for iv in intervals:
        day = datetime.date.fromisoformat(iv.end_date)
        quantity = iv.distance_km / 100.0 * rate

        if electric:
            unit_price, as_of, is_estimate = _price_electric(db, user_id, day, fallback)
        else:
            unit_price, as_of, is_estimate = _price_liquid(
                db, day, iv.location_city or "", kind, country, fallback
            )

        if as_of is None and unit_price is not None:
            used_fallback = True

        cost = round(quantity * unit_price, 2) if unit_price is not None else None
        if cost is not None:
            total += cost

        priced.append(
            PricedInterval(
                start_date=iv.start_date,
                end_date=iv.end_date,
                distance_km=iv.distance_km,
                quantity=round(quantity, 2),
                unit_price=unit_price,
                cost=cost,
                price_as_of=as_of,
                price_is_estimate=is_estimate,
            )
        )

    total_quantity = sum(p.quantity for p in priced)
    alternative_co2 = (
        emissions.from_kwh(total_quantity)
        if electric
        else emissions.from_litres(total_quantity, comparison_vehicle.fuel_type)
    )
    # Already computed per interval for the car actually driven.
    actual_co2 = sum(getattr(i, "co2_g", None) or 0 for i in intervals)

    distance = round(sum(i.distance_km for i in intervals), 2)
    # Only intervals count: the first fill paid for driving that predates the
    # log, so it has no distance here to be priced against.
    actual = round(sum(i.cost or 0 for i in intervals), 2)
    alternative = round(total, 2)

    return Comparison(
        distance_km=distance,
        actual_cost=actual,
        alternative_cost=alternative,
        saving=round(alternative - actual, 2),
        actual_cost_per_100km=round(actual / distance * 100, 2) if distance else None,
        alternative_cost_per_100km=(
            round(alternative / distance * 100, 2) if distance else None
        ),
        actual_co2_kg=round(actual_co2 / 1000, 2) if actual_co2 else None,
        alternative_co2_kg=round(alternative_co2 / 1000, 2),
        co2_saving_kg=round((alternative_co2 - actual_co2) / 1000, 2),
        actual_co2_g_per_km=round(actual_co2 / distance, 1) if distance and actual_co2 else None,
        alternative_co2_g_per_km=(
            round(alternative_co2 / distance, 1) if distance and alternative_co2 else None
        ),
        grid_co2_g_per_kwh=emissions.grid_intensity(),
        quantity=round(total_quantity, 2),
        unit=unit,
        unit_label=unit_label,
        basis=rate,
        basis_label=basis_label,
        comparison_vehicle=f"{comparison_vehicle.make} {comparison_vehicle.model}",
        comparison_fuel=comparison_vehicle.fuel_type,
        unpriced_intervals=sum(1 for p in priced if p.cost is None),
        used_fallback_price=used_fallback,
        intervals=priced,
    )
