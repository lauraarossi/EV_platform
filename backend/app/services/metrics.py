"""Derived metrics for a vehicle's charge history.

Nothing here is stored. Distance and energy come from *pairs* of consecutive
charges: the odometer closes off the interval, and the state-of-charge pair
says how much energy was actually used over it.

Why SoC rather than kWh added: the classic fuel-tracking method ("energy added
= energy consumed since the last fill") only holds if you refill to the same
level every time. EV owners routinely charge to 80%, occasionally 100%, and
sometimes less, so kWh added also covers any change in the reserve being
carried. Using the SoC drop between charges removes that error.
"""

from dataclasses import dataclass, asdict
from app.models.charging_session import ChargingSession
from app.models.vehicle import Vehicle


@dataclass
class Interval:
    """The driving between two consecutive charges."""

    from_session_id: int
    to_session_id: int
    start_date: str
    end_date: str
    distance_km: float
    kwh_added: float
    cost: float | None
    energy_used_kwh: float | None
    energy_is_exact: bool
    efficiency_kwh_per_100km: float | None
    cost_per_100km: float | None
    driving_mix: str | None
    location_city: str | None


@dataclass
class Summary:
    session_count: int
    interval_count: int
    total_distance_km: float
    total_kwh_added: float
    total_cost: float
    # Energy consumed across measured intervals; exact where SoC was recorded.
    total_energy_used_kwh: float | None
    energy_is_exact: bool
    avg_efficiency_kwh_per_100km: float | None
    avg_cost_per_100km: float | None
    avg_price_per_kwh: float | None
    latest_odometer_km: float | None
    anomalies: list[str]


def _chronological(sessions: list[ChargingSession]) -> list[ChargingSession]:
    import datetime

    return sorted(
        sessions,
        key=lambda s: (s.date, s.time_of_day or datetime.time.min, s.id),
    )


def build_intervals(
    sessions: list[ChargingSession], vehicle: Vehicle | None
) -> tuple[list[Interval], list[str]]:
    ordered = _chronological(sessions)
    battery = vehicle.battery_capacity_kwh if vehicle else None

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
            # Two charges at the same reading (e.g. topping up twice in a row);
            # no driving happened, so there is no efficiency to report.
            continue

        # Exact when we know the battery size and both ends of the SoC swing.
        energy: float | None = None
        exact = False
        if battery and prev.soc_end_pct is not None and cur.soc_start_pct is not None:
            drop = prev.soc_end_pct - cur.soc_start_pct
            if drop > 0:
                energy = drop / 100.0 * battery
                exact = True
            else:
                anomalies.append(
                    f"State of charge did not fall between {prev.date} and {cur.date}; "
                    "efficiency for that interval falls back to energy added."
                )
        if energy is None:
            energy = cur.kwh_added  # approximation

        intervals.append(
            Interval(
                from_session_id=prev.id,
                to_session_id=cur.id,
                start_date=prev.date.isoformat(),
                end_date=cur.date.isoformat(),
                distance_km=round(distance, 2),
                kwh_added=cur.kwh_added,
                cost=cur.cost,
                energy_used_kwh=round(energy, 3),
                energy_is_exact=exact,
                efficiency_kwh_per_100km=round(energy / distance * 100, 2),
                cost_per_100km=round(cur.cost / distance * 100, 2) if cur.cost is not None else None,
                driving_mix=cur.driving_mix.value if cur.driving_mix else None,
                location_city=cur.location_city,
            )
        )

    return intervals, anomalies


def summarise(sessions: list[ChargingSession], vehicle: Vehicle | None) -> Summary:
    ordered = _chronological(sessions)
    intervals, anomalies = build_intervals(sessions, vehicle)

    total_distance = sum(i.distance_km for i in intervals)
    total_energy = sum(i.energy_used_kwh or 0 for i in intervals)
    # Cost/energy attributed to measured intervals only — the very first charge
    # paid for driving that predates the log, so counting it would understate
    # efficiency and overstate cost per km.
    interval_cost = sum(i.cost or 0 for i in intervals)

    # Billing figures use every session, since they are about what was paid.
    all_kwh = sum(s.kwh_added for s in ordered)
    all_cost = sum(s.cost or 0 for s in ordered)

    return Summary(
        session_count=len(ordered),
        interval_count=len(intervals),
        total_distance_km=round(total_distance, 2),
        total_kwh_added=round(all_kwh, 3),
        total_cost=round(all_cost, 2),
        total_energy_used_kwh=round(total_energy, 3) if intervals else None,
        energy_is_exact=bool(intervals) and all(i.energy_is_exact for i in intervals),
        avg_efficiency_kwh_per_100km=(
            round(total_energy / total_distance * 100, 2) if total_distance > 0 else None
        ),
        avg_cost_per_100km=(
            round(interval_cost / total_distance * 100, 2) if total_distance > 0 else None
        ),
        avg_price_per_kwh=round(all_cost / all_kwh, 4) if all_kwh > 0 else None,
        latest_odometer_km=ordered[-1].odometer_km if ordered else None,
        anomalies=anomalies,
    )


def as_dict(obj) -> dict:
    return asdict(obj)
