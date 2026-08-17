"""Pricing the driving you did as though another car had done it.

The comparison is symmetric: what an EV owner pays to ask about petrol, a
diesel owner pays to ask about an EV. Both directions are exercised here,
because the whole point of the generalisation is that neither is special.
"""
import datetime

import pytest

from app.models import (
    ElectricityTariff, FuelKind, FuelPrice, FuelType, PriceSource, TariffRate, Vehicle,
)
from app.services import comparison
from tests.conftest import ensure_user

D = datetime.date


class FakeInterval:
    """Only the fields the pricer reads, so the maths is tested on its own."""

    def __init__(self, start, end, distance, cost=None, city=None):
        self.start_date, self.end_date = start, end
        self.distance_km, self.location_city = distance, city
        self.cost = cost


def add_price(db, day, price, kind=FuelKind.petrol_95, region="",
              source=PriceSource.eu_oil_bulletin):
    db.add(FuelPrice(date=day, country="IE", region=region, fuel_kind=kind,
                     price_per_litre=price, currency="EUR", source=source))
    db.commit()


def add_tariff(db, user_id, effective_from, rates, effective_to=None):
    tariff = ElectricityTariff(
        user_id=user_id, name="Home", effective_from=effective_from,
        effective_to=effective_to,
    )
    db.add(tariff)
    db.commit()
    for name, start, end, price in rates:
        db.add(TariffRate(tariff_id=tariff.id, name=name, price_per_kwh=price,
                          start_time=datetime.time(start), end_time=datetime.time(end)))
    db.commit()
    return tariff


def car(db, **kw):
    v = Vehicle(user_id=ensure_user(db).id, make=kw.pop("make", "Toyota"),
                model=kw.pop("model", "Corolla"), year=2023, **kw)
    db.add(v)
    db.commit()
    return v


# --- an EV owner asking about petrol -----------------------------------------

def test_each_interval_priced_at_the_rate_that_applied_then(db):
    """The point of storing history: June driving costs June's petrol price."""
    add_price(db, D(2026, 6, 1), 1.50)
    add_price(db, D(2026, 7, 1), 2.00)
    petrol = car(db, fuel_type=FuelType.petrol, fuel_consumption_l_per_100km=6.0)

    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-02", "2026-06-14", 100.0),
        FakeInterval("2026-07-02", "2026-07-14", 100.0),
    ], petrol)

    assert result.intervals[0].unit_price == pytest.approx(1.50)
    assert result.intervals[1].unit_price == pytest.approx(2.00)
    assert result.intervals[0].cost == pytest.approx(9.0)     # 6 L at 1.50
    assert result.intervals[1].cost == pytest.approx(12.0)    # 6 L at 2.00
    assert result.alternative_cost == pytest.approx(21.0)

    # Pricing everything at the latest rate would have overstated it.
    assert result.alternative_cost < 6.0 * 2.00 * 2


def test_uses_city_price_where_one_exists(db):
    add_price(db, D(2026, 6, 1), 1.80)
    add_price(db, D(2026, 6, 1), 1.60, region="Dublin", source=PriceSource.manual)
    petrol = car(db, fuel_type=FuelType.petrol, fuel_consumption_l_per_100km=6.0)

    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-02", "2026-06-14", 100.0, city="Dublin"),
    ], petrol)
    assert result.intervals[0].unit_price == pytest.approx(1.60)
    assert result.alternative_cost == pytest.approx(9.60)


def test_a_diesel_comparison_uses_the_diesel_price(db):
    """Not petrol's: the two have diverged by 20c a litre before now."""
    add_price(db, D(2026, 6, 1), 1.80, kind=FuelKind.petrol_95)
    add_price(db, D(2026, 6, 1), 1.60, kind=FuelKind.diesel)
    diesel = car(db, fuel_type=FuelType.diesel, fuel_consumption_l_per_100km=5.0)

    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-02", "2026-06-14", 100.0),
    ], diesel)
    assert result.intervals[0].unit_price == pytest.approx(1.60)


# --- a petrol owner asking about an EV ----------------------------------------

def test_an_electric_comparison_is_priced_from_your_tariff(db):
    user = ensure_user(db)
    add_tariff(db, user.id, D(2026, 1, 1),
               [("Day", 8, 23, 0.35), ("Night", 23, 8, 0.14)])
    ev = car(db, make="Renault", model="5 E-Tech", fuel_type=FuelType.electric,
             consumption_kwh_per_100km=15.0)

    result = comparison.compare(db, user.id, [
        FakeInterval("2026-06-02", "2026-06-14", 200.0),
    ], ev)

    assert result.unit == "kwh"
    # 200 km at 15 kWh/100km = 30 kWh, at the cheapest band.
    assert result.quantity == pytest.approx(30.0)
    assert result.intervals[0].unit_price == pytest.approx(0.14)
    assert result.alternative_cost == pytest.approx(4.20)


def test_the_tariff_version_in_force_at_the_time_is_used(db):
    """Same time-travel the pump price gets: a rate rise last spring must not
    be applied to the year before it."""
    user = ensure_user(db)
    add_tariff(db, user.id, D(2026, 1, 1), [("Flat", 0, 0, 0.20)],
               effective_to=D(2026, 5, 31))
    add_tariff(db, user.id, D(2026, 6, 1), [("Flat", 0, 0, 0.40)])
    ev = car(db, fuel_type=FuelType.electric, consumption_kwh_per_100km=20.0)

    result = comparison.compare(db, user.id, [
        FakeInterval("2026-03-01", "2026-03-10", 100.0),
        FakeInterval("2026-07-01", "2026-07-10", 100.0),
    ], ev)

    assert result.intervals[0].unit_price == pytest.approx(0.20)
    assert result.intervals[1].unit_price == pytest.approx(0.40)


def test_an_ev_without_a_consumption_figure_derives_one(db):
    """Battery over rated range is a fair stand-in, and beats refusing."""
    ev = car(db, fuel_type=FuelType.electric, battery_capacity_kwh=52.0,
             wltp_range_km=400.0)

    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-02", "2026-06-14", 100.0),
    ], ev, fallback_price_per_kwh=0.30)

    assert result.basis == pytest.approx(13.0)      # 52 / 400 * 100
    assert result.alternative_cost == pytest.approx(3.90)


def test_an_ev_with_nothing_to_go_on_is_refused_clearly(db):
    ev = car(db, fuel_type=FuelType.electric)
    with pytest.raises(comparison.CannotCompare, match="kWh/100km"):
        comparison.compare(db, ensure_user(db).id, [], ev)


def test_a_petrol_car_with_no_consumption_is_refused_clearly(db):
    petrol = car(db, fuel_type=FuelType.petrol)
    with pytest.raises(comparison.CannotCompare, match="L/100km"):
        comparison.compare(db, ensure_user(db).id, [], petrol)


# --- the saving --------------------------------------------------------------

def test_saving_is_what_the_alternative_would_have_added(db):
    add_price(db, D(2026, 6, 1), 2.00)
    petrol = car(db, fuel_type=FuelType.petrol, fuel_consumption_l_per_100km=6.0)

    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-02", "2026-06-14", 100.0, cost=4.0),
    ], petrol)

    assert result.actual_cost == pytest.approx(4.0)
    assert result.alternative_cost == pytest.approx(12.0)
    assert result.saving == pytest.approx(8.0)      # positive: you are ahead


def test_a_worse_alternative_reads_as_a_negative_saving(db):
    """The sign has to survive the comparison going the other way — an EV
    owner on a bad tariff could genuinely be behind."""
    add_price(db, D(2026, 6, 1), 1.00)
    petrol = car(db, fuel_type=FuelType.petrol, fuel_consumption_l_per_100km=4.0)

    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-02", "2026-06-14", 100.0, cost=10.0),
    ], petrol)
    assert result.saving == pytest.approx(-6.0)


# --- missing prices -----------------------------------------------------------

def test_fallback_price_is_flagged(db):
    petrol = car(db, fuel_type=FuelType.petrol, fuel_consumption_l_per_100km=6.0)
    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-02", "2026-06-14", 100.0),
    ], petrol, fallback_price_per_litre=1.79)

    assert result.used_fallback_price is True
    assert result.intervals[0].unit_price == pytest.approx(1.79)
    assert result.intervals[0].price_is_estimate is True
    assert result.alternative_cost == pytest.approx(10.74)


def test_without_price_or_fallback_cost_is_none_not_zero(db):
    """A missing price must not silently look like free driving."""
    petrol = car(db, fuel_type=FuelType.petrol, fuel_consumption_l_per_100km=6.0)
    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-02", "2026-06-14", 100.0),
    ], petrol)

    assert result.intervals[0].cost is None
    assert result.alternative_cost == 0.0
    assert result.unpriced_intervals == 1


def test_an_ev_falls_back_when_no_tariff_covers_the_date(db):
    ev = car(db, fuel_type=FuelType.electric, consumption_kwh_per_100km=15.0)
    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-02", "2026-06-14", 100.0),
    ], ev, fallback_price_per_kwh=0.30)

    assert result.used_fallback_price is True
    assert result.alternative_cost == pytest.approx(4.50)


# --- emissions ----------------------------------------------------------------
#
# The third axis: someone weighing up a car cares what it emits as well as what
# it costs, and the two do not always point the same way.

def test_petrol_emissions_come_from_litres_burned(db):
    add_price(db, D(2026, 6, 1), 1.80)
    petrol = car(db, fuel_type=FuelType.petrol, fuel_consumption_l_per_100km=6.0)

    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-02", "2026-06-14", 1000.0),
    ], petrol)

    # 60 L at 2392 g/L — a property of the fuel, not of the engine.
    assert result.alternative_co2_kg == pytest.approx(143.52, abs=0.01)
    assert result.alternative_co2_g_per_km == pytest.approx(143.5, abs=0.1)


def test_diesel_emits_more_per_litre_than_petrol(db):
    """More carbon per litre, which its better economy has to make up for."""
    petrol = car(db, fuel_type=FuelType.petrol, fuel_consumption_l_per_100km=6.0)
    diesel = car(db, make="VW", model="Golf", fuel_type=FuelType.diesel,
                 fuel_consumption_l_per_100km=6.0)
    intervals = [FakeInterval("2026-06-02", "2026-06-14", 1000.0)]

    a = comparison.compare(db, ensure_user(db).id, intervals, petrol)
    b = comparison.compare(db, ensure_user(db).id, intervals, diesel)
    assert b.alternative_co2_kg > a.alternative_co2_kg


def test_electric_emissions_depend_on_the_grid(db):
    """An EV has no tailpipe, so its emissions are the power station's and
    move with whatever the grid is running on."""
    from app.config import settings

    ev = car(db, fuel_type=FuelType.electric, consumption_kwh_per_100km=15.0)
    intervals = [FakeInterval("2026-06-02", "2026-06-14", 1000.0)]

    clean = settings.grid_co2_g_per_kwh
    try:
        settings.grid_co2_g_per_kwh = 100.0
        low = comparison.compare(db, ensure_user(db).id, intervals, ev)
        settings.grid_co2_g_per_kwh = 400.0
        high = comparison.compare(db, ensure_user(db).id, intervals, ev)
    finally:
        settings.grid_co2_g_per_kwh = clean

    assert low.alternative_co2_kg == pytest.approx(15.0)    # 150 kWh at 100 g
    assert high.alternative_co2_kg == pytest.approx(60.0)   # at 400 g
    assert high.grid_co2_g_per_kwh == 400.0


def test_emissions_are_reported_without_a_price(db):
    """Cost needs a price series; CO2 does not, so a missing price must not
    take the emissions figure down with it."""
    petrol = car(db, fuel_type=FuelType.petrol, fuel_consumption_l_per_100km=6.0)

    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-02", "2026-06-14", 100.0),
    ], petrol)

    assert result.alternative_cost == 0.0 and result.unpriced_intervals == 1
    assert result.alternative_co2_kg > 0
