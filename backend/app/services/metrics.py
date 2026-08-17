"""Derived metrics for a vehicle's refuelling history.

Nothing here is stored. Distance and consumption come from *pairs* of
consecutive events: the odometer closes off the interval, and the level either
side says how much was actually used over it.

Why the level rather than what went in: the classic fuel-tracking method
("what went in is what came out since the last fill") only holds if you refill
to the same level every time. Nobody does. EV owners charge to 80%, sometimes
100%, sometimes less; a driver puts €30 in rather than filling the tank. What
went in then also covers any change in the reserve being carried, and that
error lands entirely on the interval.

The maths is identical for electricity and liquid fuel — a percentage of a
capacity — so both run through the same helper. A plug-in hybrid uses both at
once, which is why the two are tracked side by side rather than merged.
"""

from dataclasses import dataclass, asdict

from app.models.fuel_event import FuelEvent
from app.models.vehicle import Vehicle
from app.services import emissions


@dataclass
class Interval:
    """The driving between two consecutive refuelling events."""

    from_event_id: int
    to_event_id: int
    start_date: str
    end_date: str
    distance_km: float
    cost: float | None

    # Electric side
    energy_added_kwh: float | None
    energy_used_kwh: float | None
    energy_is_exact: bool
    efficiency_kwh_per_100km: float | None

    # Liquid-fuel side
    volume_added_litres: float | None
    volume_used_litres: float | None
    volume_is_exact: bool
    consumption_l_per_100km: float | None

    # Burning the fuel and generating the electricity, not the full lifecycle.
    co2_g: float | None
    co2_g_per_km: float | None

    cost_per_100km: float | None
    driving_mix: str | None
    location_city: str | None


@dataclass
class Summary:
    event_count: int
    interval_count: int
    total_distance_km: float
    total_cost: float

    total_energy_added_kwh: float
    total_energy_used_kwh: float | None
    energy_is_exact: bool
    avg_efficiency_kwh_per_100km: float | None
    avg_price_per_kwh: float | None

    total_volume_added_litres: float
    total_volume_used_litres: float | None
    volume_is_exact: bool
    avg_consumption_l_per_100km: float | None
    avg_price_per_litre: float | None

    total_co2_kg: float | None
    avg_co2_g_per_km: float | None

    avg_cost_per_100km: float | None
    latest_odometer_km: float | None
    anomalies: list[str]


def _chronological(events: list[FuelEvent]) -> list[FuelEvent]:
    import datetime

    return sorted(
        events,
        key=lambda e: (e.date, e.time_of_day or datetime.time.min, e.id),
    )


def _used(
    capacity: float | None,
    level_end_prev: float | None,
    level_start_cur: float | None,
    added: float | None,
) -> tuple[float | None, bool, bool]:
    """How much was consumed over one interval.

    Returns (amount, whether it is exact, whether the levels looked wrong).
    Exact needs the capacity and both ends of the swing; otherwise it falls
    back to what went in, which is an approximation.
    """
    if capacity and level_end_prev is not None and level_start_cur is not None:
        drop = level_end_prev - level_start_cur
        if drop > 0:
            return drop / 100.0 * capacity, True, False
        # A level that rose or held between fills cannot be right.
        return (added, False, True) if added else (None, False, True)
    return (added, False, False) if added else (None, False, False)


def build_intervals(
    events: list[FuelEvent], vehicle: Vehicle | None
) -> tuple[list[Interval], list[str]]:
    ordered = _chronological(events)
    battery = vehicle.battery_capacity_kwh if vehicle else None
    tank = vehicle.tank_capacity_litres if vehicle else None

    intervals: list[Interval] = []
    anomalies: list[str] = []

    for prev, cur in zip(ordered, ordered[1:]):
        distance = cur.odometer_km - prev.odometer_km

        if distance < 0:
            anomalies.append(
                f"Odometer went backwards between {prev.date} and {cur.date} "
                f"({prev.odometer_km} → {cur.odometer_km} km)."
            )
            continue
        if distance == 0:
            # Two fills at the same reading (topping up twice in a row); no
            # driving happened, so there is no consumption to report.
            continue

        energy, energy_exact, soc_odd = _used(
            battery, prev.soc_end_pct, cur.soc_start_pct, cur.energy_kwh
        )
        volume, volume_exact, tank_odd = _used(
            tank, prev.tank_end_pct, cur.tank_start_pct, cur.volume_litres
        )
        if soc_odd:
            anomalies.append(
                f"State of charge did not fall between {prev.date} and {cur.date}; "
                "that interval falls back to the energy added."
            )
        if tank_odd:
            anomalies.append(
                f"Fuel level did not fall between {prev.date} and {cur.date}; "
                "that interval falls back to the fuel added."
            )

        co2 = emissions.total(energy, volume, vehicle.fuel_type if vehicle else None)

        intervals.append(
            Interval(
                from_event_id=prev.id,
                to_event_id=cur.id,
                start_date=prev.date.isoformat(),
                end_date=cur.date.isoformat(),
                distance_km=round(distance, 2),
                cost=cur.cost,
                energy_added_kwh=cur.energy_kwh,
                energy_used_kwh=round(energy, 3) if energy is not None else None,
                energy_is_exact=energy_exact,
                efficiency_kwh_per_100km=(
                    round(energy / distance * 100, 2) if energy is not None else None
                ),
                volume_added_litres=cur.volume_litres,
                volume_used_litres=round(volume, 3) if volume is not None else None,
                volume_is_exact=volume_exact,
                consumption_l_per_100km=(
                    round(volume / distance * 100, 2) if volume is not None else None
                ),
                co2_g=round(co2, 1) if co2 else None,
                co2_g_per_km=round(co2 / distance, 1) if co2 else None,
                cost_per_100km=(
                    round(cur.cost / distance * 100, 2) if cur.cost is not None else None
                ),
                driving_mix=cur.driving_mix.value if cur.driving_mix else None,
                location_city=cur.location_city,
            )
        )

    return intervals, anomalies


def _avg(total: float, distance: float) -> float | None:
    return round(total / distance * 100, 2) if distance > 0 and total else None


def summarise(events: list[FuelEvent], vehicle: Vehicle | None) -> Summary:
    ordered = _chronological(events)
    intervals, anomalies = build_intervals(events, vehicle)

    total_distance = sum(i.distance_km for i in intervals)
    energy_used = sum(i.energy_used_kwh or 0 for i in intervals)
    volume_used = sum(i.volume_used_litres or 0 for i in intervals)

    # Cost is attributed to measured intervals only: the very first fill paid
    # for driving that predates the log, so counting it would overstate cost
    # per km against a distance that does not include that driving.
    interval_cost = sum(i.cost or 0 for i in intervals)

    # Billing figures use every event, since they are about what was paid.
    all_energy = sum(e.energy_kwh or 0 for e in ordered)
    all_volume = sum(e.volume_litres or 0 for e in ordered)
    all_cost = sum(e.cost or 0 for e in ordered)

    total_co2 = sum(i.co2_g or 0 for i in intervals)
    measured = [i for i in intervals if i.energy_used_kwh is not None]
    fuelled = [i for i in intervals if i.volume_used_litres is not None]

    return Summary(
        event_count=len(ordered),
        interval_count=len(intervals),
        total_distance_km=round(total_distance, 2),
        total_cost=round(all_cost, 2),
        total_energy_added_kwh=round(all_energy, 3),
        total_energy_used_kwh=round(energy_used, 3) if measured else None,
        energy_is_exact=bool(measured) and all(i.energy_is_exact for i in measured),
        avg_efficiency_kwh_per_100km=_avg(energy_used, total_distance),
        avg_price_per_kwh=(
            round(all_cost / all_energy, 4) if all_energy and not all_volume else None
        ),
        total_volume_added_litres=round(all_volume, 3),
        total_volume_used_litres=round(volume_used, 3) if fuelled else None,
        volume_is_exact=bool(fuelled) and all(i.volume_is_exact for i in fuelled),
        avg_consumption_l_per_100km=_avg(volume_used, total_distance),
        avg_price_per_litre=(
            round(all_cost / all_volume, 4) if all_volume and not all_energy else None
        ),
        total_co2_kg=round(total_co2 / 1000, 2) if total_co2 else None,
        avg_co2_g_per_km=(
            round(total_co2 / total_distance, 1) if total_distance > 0 and total_co2 else None
        ),
        avg_cost_per_100km=_avg(interval_cost, total_distance),
        latest_odometer_km=ordered[-1].odometer_km if ordered else None,
        anomalies=anomalies,
    )


def as_dict(obj) -> dict:
    return asdict(obj)
