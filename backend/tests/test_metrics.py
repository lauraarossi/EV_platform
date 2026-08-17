"""Tests for the derived-metrics maths.

The scenario deliberately uses *varying* charge targets (80%, then 100% for a
road trip, then 60%), because that is the case where the naive fuel-tracking
method — "energy added = energy consumed since the last fill" — silently gives
the wrong answer for an EV.
"""
import datetime
import pytest

from app.models import Vehicle, FuelEvent, ChargerType, DrivingMix, FuelType
from tests.conftest import ensure_user
from app.services import metrics

BATTERY_KWH = 52.0

# `db` comes from tests/conftest.py


def make_vehicle(db, battery=BATTERY_KWH):
    owner = ensure_user(db)
    v = Vehicle(make="Renault", model="R4 E-Tech", year=2025, battery_capacity_kwh=battery,
                user_id=owner.id)
    db.add(v)
    db.commit()
    return v


def add_charge(db, vehicle, day, odo, kwh, cost=None, soc_in=None, soc_out=None, mix=None):
    db.add(
        FuelEvent(
            vehicle_id=vehicle.id,
            date=datetime.date(2026, 1, day),
            odometer_km=odo,
            energy_kwh=kwh,
            cost=cost,
            soc_start_pct=soc_in,
            soc_end_pct=soc_out,
            charger_type=ChargerType.ac_home,
            driving_mix=mix,
        )
    )
    db.commit()


@pytest.fixture
def varied_targets(db):
    """80% → 100% (road trip) → 60%: the awkward real-world pattern."""
    v = make_vehicle(db)
    add_charge(db, v, 1, 10_000, 26.0, 6.50, 30, 80, DrivingMix.city)
    add_charge(db, v, 8, 10_250, 31.2, 7.80, 20, 80, DrivingMix.city)
    add_charge(db, v, 15, 10_600, 41.6, 12.00, 20, 100, DrivingMix.motorway)
    add_charge(db, v, 22, 10_800, 20.8, 5.20, 60, 100, DrivingMix.mixed)
    return v, db.query(FuelEvent).all()


def test_intervals_match_hand_computed_values(varied_targets):
    vehicle, sessions = varied_targets
    intervals, anomalies = metrics.build_intervals(sessions, vehicle)

    assert not anomalies
    assert len(intervals) == 3

    # (distance, energy consumed, efficiency) worked out by hand:
    #   80→20 = 60% of 52kWh = 31.2kWh over 250km -> 12.48
    #   80→20 = 60% of 52kWh = 31.2kWh over 350km ->  8.91
    #  100→60 = 40% of 52kWh = 20.8kWh over 200km -> 10.40
    expected = [(250.0, 31.2, 12.48), (350.0, 31.2, 8.91), (200.0, 20.8, 10.40)]
    for got, (dist, energy, eff) in zip(intervals, expected):
        assert got.distance_km == pytest.approx(dist)
        assert got.energy_used_kwh == pytest.approx(energy, abs=0.01)
        assert got.efficiency_kwh_per_100km == pytest.approx(eff, abs=0.01)
        assert got.energy_is_exact


def test_soc_corrects_road_trip_topup_distortion(varied_targets):
    """Charging to 100% once must not make that interval look inefficient."""
    vehicle, sessions = varied_targets
    intervals, _ = metrics.build_intervals(sessions, vehicle)

    road_trip = intervals[1]
    naive = 41.6 / 350 * 100  # what "kWh added / distance" would claim

    assert naive == pytest.approx(11.89, abs=0.01)
    assert road_trip.efficiency_kwh_per_100km == pytest.approx(8.91, abs=0.01)
    assert naive > road_trip.efficiency_kwh_per_100km


def test_summary_totals(varied_targets):
    vehicle, sessions = varied_targets
    s = metrics.summarise(sessions, vehicle)

    assert s.event_count == 4
    assert s.interval_count == 3
    assert s.total_distance_km == pytest.approx(800.0)
    assert s.total_energy_used_kwh == pytest.approx(83.2, abs=0.01)
    assert s.avg_efficiency_kwh_per_100km == pytest.approx(10.4, abs=0.01)
    assert s.latest_odometer_km == 10_800
    assert s.energy_is_exact
    assert not s.anomalies


def test_first_charge_excluded_from_interval_cost(varied_targets):
    """The first charge paid for driving that predates the log, so counting it
    would overstate cost per km."""
    vehicle, sessions = varied_targets
    s = metrics.summarise(sessions, vehicle)

    interval_cost = 7.80 + 12.00 + 5.20  # excludes the first charge's 6.50
    assert s.avg_cost_per_100km == pytest.approx(interval_cost / 800 * 100, abs=0.01)
    # Billing figures, by contrast, count every charge.
    assert s.total_cost == pytest.approx(31.50)


def test_falls_back_to_kwh_added_when_soc_missing(db):
    v = make_vehicle(db)
    add_charge(db, v, 1, 0, 20.0)
    add_charge(db, v, 8, 200, 30.0)

    intervals, _ = metrics.build_intervals(db.query(FuelEvent).all(), v)
    assert len(intervals) == 1
    assert not intervals[0].energy_is_exact
    assert intervals[0].efficiency_kwh_per_100km == pytest.approx(15.0)


def test_falls_back_when_battery_capacity_unknown(db):
    v = make_vehicle(db, battery=None)
    add_charge(db, v, 1, 0, 20.0, soc_in=20, soc_out=80)
    add_charge(db, v, 8, 200, 30.0, soc_in=20, soc_out=80)

    intervals, _ = metrics.build_intervals(db.query(FuelEvent).all(), v)
    assert len(intervals) == 1
    assert not intervals[0].energy_is_exact


def test_backwards_odometer_is_flagged_not_negative(db):
    v = make_vehicle(db)
    add_charge(db, v, 1, 500, 10.0)
    add_charge(db, v, 2, 400, 10.0)

    intervals, anomalies = metrics.build_intervals(db.query(FuelEvent).all(), v)
    assert intervals == []
    assert len(anomalies) == 1
    assert "backwards" in anomalies[0]


def test_two_charges_same_odometer_produce_no_interval(db):
    """Topping up twice without driving is not a zero-efficiency interval."""
    v = make_vehicle(db)
    add_charge(db, v, 1, 1000, 10.0, soc_in=30, soc_out=60)
    add_charge(db, v, 1, 1000, 5.0, soc_in=60, soc_out=80)

    intervals, anomalies = metrics.build_intervals(db.query(FuelEvent).all(), v)
    assert intervals == []
    assert not anomalies


def test_single_charge_has_no_intervals(db):
    v = make_vehicle(db)
    add_charge(db, v, 1, 1000, 10.0)

    s = metrics.summarise(db.query(FuelEvent).all(), v)
    assert s.interval_count == 0
    assert s.total_distance_km == 0
    assert s.avg_efficiency_kwh_per_100km is None
    assert s.latest_odometer_km == 1000


def test_no_events_at_all(db):
    v = make_vehicle(db)
    s = metrics.summarise([], v)
    assert s.event_count == 0
    assert s.latest_odometer_km is None
    assert s.avg_efficiency_kwh_per_100km is None


# --- the same maths, for a car that burns petrol ------------------------------
#
# The generalisation's claim is that a tank is a battery: a percentage of a
# capacity. These mirror the EV cases above deliberately, including the partial
# fill that the naive method gets wrong.

TANK_LITRES = 50.0


def make_petrol_car(db, tank=TANK_LITRES):
    owner = ensure_user(db)
    v = Vehicle(make="Toyota", model="Corolla", year=2022, fuel_type=FuelType.petrol,
                tank_capacity_litres=tank, user_id=owner.id)
    db.add(v)
    db.commit()
    return v


def add_fillup(db, vehicle, day, odo, litres, cost=None, tank_in=None, tank_out=None):
    db.add(
        FuelEvent(
            vehicle_id=vehicle.id,
            date=datetime.date(2026, 1, day),
            odometer_km=odo,
            volume_litres=litres,
            cost=cost,
            tank_start_pct=tank_in,
            tank_end_pct=tank_out,
        )
    )
    db.commit()


def test_tank_levels_make_petrol_consumption_exact(db):
    v = make_petrol_car(db)
    add_fillup(db, v, 1, 20_000, 35.0, 60.00, 20, 90)
    # Filled to full after a partial: 90% down to 25% is 32.5 L over 500 km.
    add_fillup(db, v, 15, 20_500, 37.5, 65.00, 25, 100)

    intervals, anomalies = metrics.build_intervals(db.query(FuelEvent).all(), v)

    assert not anomalies
    assert intervals[0].volume_used_litres == pytest.approx(32.5, abs=0.01)
    assert intervals[0].consumption_l_per_100km == pytest.approx(6.5, abs=0.01)
    assert intervals[0].volume_is_exact


def test_a_partial_fill_would_have_misreported_consumption(db):
    """The petrol equivalent of the road-trip distortion: topping up €30 worth
    reports less fuel than was burned, unless the levels are recorded."""
    v = make_petrol_car(db)
    add_fillup(db, v, 1, 20_000, 40.0, tank_in=10, tank_out=90)
    add_fillup(db, v, 15, 20_500, 20.0, tank_in=25, tank_out=65)

    intervals, _ = metrics.build_intervals(db.query(FuelEvent).all(), v)

    naive = 20.0 / 500 * 100          # what "litres added / distance" claims
    assert naive == pytest.approx(4.0)
    assert intervals[0].consumption_l_per_100km == pytest.approx(6.5, abs=0.01)
    assert naive < intervals[0].consumption_l_per_100km


def test_petrol_falls_back_to_litres_added_without_levels(db):
    v = make_petrol_car(db)
    add_fillup(db, v, 1, 0, 30.0)
    add_fillup(db, v, 15, 500, 32.5)

    intervals, _ = metrics.build_intervals(db.query(FuelEvent).all(), v)
    assert not intervals[0].volume_is_exact
    assert intervals[0].consumption_l_per_100km == pytest.approx(6.5, abs=0.01)


def test_petrol_summary_reports_litres_not_kwh(db):
    v = make_petrol_car(db)
    add_fillup(db, v, 1, 20_000, 35.0, 60.00, 20, 90)
    add_fillup(db, v, 15, 20_500, 37.5, 65.00, 25, 100)

    s = metrics.summarise(db.query(FuelEvent).all(), v)

    assert s.avg_consumption_l_per_100km == pytest.approx(6.5, abs=0.01)
    assert s.avg_efficiency_kwh_per_100km is None
    assert s.total_volume_added_litres == pytest.approx(72.5)
    assert s.avg_price_per_litre == pytest.approx(125.0 / 72.5, abs=0.001)


def test_a_plug_in_hybrid_tracks_both_at_once(db):
    """One stop can add electricity and petrol, and each has its own level
    pair — a single "level" column could not say which it described."""
    owner = ensure_user(db)
    v = Vehicle(make="Toyota", model="Prius", year=2024, fuel_type=FuelType.hybrid,
                battery_capacity_kwh=13.6, tank_capacity_litres=40.0, user_id=owner.id)
    db.add(v)
    db.commit()

    for day, odo, soc_in, soc_out, tank_in, tank_out in (
        (1, 30_000, 20, 100, 30, 100),
        (15, 30_400, 40, 100, 60, 100),
    ):
        db.add(FuelEvent(vehicle_id=v.id, date=datetime.date(2026, 1, day), odometer_km=odo,
                         energy_kwh=10.0, volume_litres=16.0,
                         soc_start_pct=soc_in, soc_end_pct=soc_out,
                         tank_start_pct=tank_in, tank_end_pct=tank_out))
    db.commit()

    iv = metrics.build_intervals(db.query(FuelEvent).all(), v)[0][0]

    # 100→40 of 13.6 kWh, and 100→60 of 40 L, over the same 400 km.
    assert iv.energy_used_kwh == pytest.approx(8.16, abs=0.01)
    assert iv.volume_used_litres == pytest.approx(16.0, abs=0.01)
    assert iv.efficiency_kwh_per_100km == pytest.approx(2.04, abs=0.01)
    assert iv.consumption_l_per_100km == pytest.approx(4.0, abs=0.01)
    assert iv.energy_is_exact and iv.volume_is_exact


def test_an_ev_summary_has_no_litres(db):
    v = make_vehicle(db)
    add_charge(db, v, 1, 0, 20.0, soc_in=20, soc_out=80)
    add_charge(db, v, 8, 200, 30.0, soc_in=20, soc_out=80)

    s = metrics.summarise(db.query(FuelEvent).all(), v)
    assert s.avg_consumption_l_per_100km is None
    assert s.total_volume_added_litres == 0
