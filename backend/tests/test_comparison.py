"""Pricing the same driving in two cars, on equal terms.

Both sides use the consumption figure entered for that car, and the same unit
price wherever the fuels match. Nothing is scaled, adjusted or inferred — so
the answer is about the two cars, not about how the numbers were arrived at.

The comparison is symmetric: what an EV owner asks about petrol, a diesel owner
asks about an EV, and neither side is special.
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

    def __init__(self, start, end, distance, cost=None, city=None,
                 litres_added=None, kwh_added=None):
        self.start_date, self.end_date = start, end
        self.distance_km, self.location_city = distance, city
        self.cost = cost
        self.volume_added_litres = litres_added
        self.energy_added_kwh = kwh_added


def add_price(db, day, price, kind=FuelKind.petrol_95, region="",
              source=PriceSource.eu_oil_bulletin):
    db.add(FuelPrice(date=day, country="IE", region=region, fuel_kind=kind,
                     price_per_litre=price, currency="EUR", source=source))
    db.commit()


def add_tariff(db, user_id, effective_from, rates, effective_to=None):
    tariff = ElectricityTariff(user_id=user_id, name="Home", effective_from=effective_from,
                               effective_to=effective_to)
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


def petrol(db, l_per_100km, **kw):
    return car(db, fuel_type=FuelType.petrol, fuel_consumption_l_per_100km=l_per_100km, **kw)


# --- the figures entered are the figures used ---------------------------------

def test_two_cars_quoted_the_same_compare_identically(db):
    """The property everything else rests on. Anything that made an identical
    car look better would be measuring the method, not the cars."""
    mine = petrol(db, 7.0, make="Audi", model="A4")
    theirs = petrol(db, 7.0, make="Audi", model="A4")

    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-01", "2026-06-20", 500.0, cost=90.0, litres_added=45.0),
    ], theirs, driven_vehicle=mine)

    assert result.co2_saving_kg == 0.0
    assert result.saving == 0.0
    assert result.actual_co2_kg == result.alternative_co2_kg


def test_the_same_car_entered_differently_compares_differently(db):
    """Two of the same model, one entered thirstier — a heavier right foot, or
    a roof box that lives on it. The difference must follow what was typed."""
    mine = petrol(db, 8.0, make="Audi", model="A4")
    theirs = petrol(db, 6.0, make="Audi", model="A4")

    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-01", "2026-06-20", 1000.0, cost=160.0, litres_added=80.0),
    ], theirs, driven_vehicle=mine)

    assert result.your_basis == 8.0 and result.basis == 6.0
    assert result.your_quantity == pytest.approx(80.0)      # 8.0 over 1000 km
    assert result.quantity == pytest.approx(60.0)           # 6.0 over 1000 km
    # A quarter less fuel, so a quarter less of both cost and CO2.
    assert result.saving == pytest.approx(-40.0)            # 20 L at EUR 2.00
    assert result.co2_saving_kg == pytest.approx(-47.84, abs=0.01)


def test_nothing_is_scaled_by_how_you_actually_drive(db):
    """Measured consumption belongs on the Stats page. Letting it inflate one
    side here made an identical car look 30 kg cleaner over 500 km."""
    mine = petrol(db, 6.5)
    theirs = petrol(db, 6.5)

    # Actually burning far more than quoted must not change the comparison.
    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-01", "2026-06-20", 500.0, cost=90.0, litres_added=45.0),
    ], theirs, driven_vehicle=mine)

    assert result.saving == 0.0
    assert result.your_basis == result.basis == 6.5


# --- prices -------------------------------------------------------------------

def test_both_cars_are_priced_at_what_you_actually_paid(db):
    """Your receipt beats any national average, and using it on both sides is
    what keeps the two comparable."""
    mine = petrol(db, 5.0)
    theirs = petrol(db, 10.0)

    result = comparison.compare(db, ensure_user(db).id, [
        # EUR 90 for 45 L is EUR 2.00 a litre.
        FakeInterval("2026-06-01", "2026-06-20", 1000.0, cost=90.0, litres_added=45.0),
    ], theirs, driven_vehicle=mine)

    assert result.intervals[0].unit_price == pytest.approx(2.00)
    assert result.actual_cost == pytest.approx(100.0)        # 50 L at 2.00
    assert result.alternative_cost == pytest.approx(200.0)   # 100 L at 2.00
    assert result.intervals[0].price_is_estimate is False


def test_the_feed_fills_in_when_a_fill_had_no_cost(db):
    add_price(db, D(2026, 6, 1), 1.80)
    mine = petrol(db, 6.0)
    theirs = petrol(db, 6.0)

    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-02", "2026-06-14", 100.0, litres_added=6.0),
    ], theirs, driven_vehicle=mine)
    assert result.intervals[0].unit_price == pytest.approx(1.80)


def test_each_interval_keeps_the_price_of_its_own_time(db):
    """June driving costs June's petrol, not this week's."""
    mine = petrol(db, 6.0)
    theirs = petrol(db, 6.0)

    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-02", "2026-06-14", 100.0, cost=9.0, litres_added=6.0),
        FakeInterval("2026-07-02", "2026-07-14", 100.0, cost=12.0, litres_added=6.0),
    ], theirs, driven_vehicle=mine)

    assert result.intervals[0].unit_price == pytest.approx(1.50)
    assert result.intervals[1].unit_price == pytest.approx(2.00)


def test_spend_is_reported_separately_from_the_comparison(db):
    """Real money from the receipts, kept apart from the like-for-like sum,
    which is modelled from the entered figures."""
    mine = petrol(db, 5.0)
    theirs = petrol(db, 5.0)

    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-01", "2026-06-20", 500.0, cost=90.0, litres_added=45.0),
    ], theirs, driven_vehicle=mine)

    assert result.actual_spend == pytest.approx(90.0)        # what you handed over
    assert result.actual_cost == pytest.approx(50.0)         # 25 L at 2.00, as quoted
    assert result.saving == 0.0


# --- across fuels -------------------------------------------------------------

def test_a_diesel_comparison_uses_the_diesel_price(db):
    """Not petrol's, and not yours: a different fuel needs its own market rate."""
    add_price(db, D(2026, 6, 1), 1.60, kind=FuelKind.diesel)
    mine = petrol(db, 6.0)
    theirs = car(db, fuel_type=FuelType.diesel, fuel_consumption_l_per_100km=5.0)

    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-02", "2026-06-14", 100.0, cost=12.0, litres_added=6.0),
    ], theirs, driven_vehicle=mine)
    assert result.intervals[0].unit_price == pytest.approx(1.60)


def test_an_electric_comparison_is_priced_from_your_tariff(db):
    user = ensure_user(db)
    add_tariff(db, user.id, D(2026, 1, 1), [("Day", 8, 23, 0.35), ("Night", 23, 8, 0.14)])
    mine = petrol(db, 6.0)
    ev = car(db, make="Renault", model="5 E-Tech", fuel_type=FuelType.electric,
             consumption_kwh_per_100km=15.0)

    result = comparison.compare(db, user.id, [
        FakeInterval("2026-06-02", "2026-06-14", 200.0, cost=24.0, litres_added=12.0),
    ], ev, driven_vehicle=mine)

    assert result.unit == "kwh"
    assert result.quantity == pytest.approx(30.0)            # 200 km at 15/100
    assert result.intervals[0].unit_price == pytest.approx(0.14)
    assert result.alternative_cost == pytest.approx(4.20)


def test_the_tariff_version_in_force_at_the_time_is_used(db):
    user = ensure_user(db)
    add_tariff(db, user.id, D(2026, 1, 1), [("Flat", 0, 0, 0.20)], effective_to=D(2026, 5, 31))
    add_tariff(db, user.id, D(2026, 6, 1), [("Flat", 0, 0, 0.40)])
    mine = petrol(db, 6.0)
    ev = car(db, fuel_type=FuelType.electric, consumption_kwh_per_100km=20.0)

    result = comparison.compare(db, user.id, [
        FakeInterval("2026-03-01", "2026-03-10", 100.0),
        FakeInterval("2026-07-01", "2026-07-10", 100.0),
    ], ev, driven_vehicle=mine)

    assert result.intervals[0].unit_price == pytest.approx(0.20)
    assert result.intervals[1].unit_price == pytest.approx(0.40)


def test_an_ev_without_a_consumption_figure_derives_one(db):
    """Battery over rated range is a fair stand-in, and beats refusing."""
    mine = petrol(db, 6.0)
    ev = car(db, fuel_type=FuelType.electric, battery_capacity_kwh=52.0, wltp_range_km=400.0)

    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-02", "2026-06-14", 100.0),
    ], ev, driven_vehicle=mine, fallback_price_per_kwh=0.30)

    assert result.basis == pytest.approx(13.0)               # 52 / 400 * 100
    assert result.alternative_cost == pytest.approx(3.90)


@pytest.mark.parametrize("missing_side", ["yours", "theirs"])
def test_a_missing_consumption_figure_is_refused_clearly(db, missing_side):
    """Either side without one and there is nothing to compare."""
    good = petrol(db, 6.0)
    bare = car(db, fuel_type=FuelType.petrol)
    mine, theirs = (bare, good) if missing_side == "yours" else (good, bare)

    with pytest.raises(comparison.CannotCompare, match="L/100km"):
        comparison.compare(db, ensure_user(db).id, [], theirs, driven_vehicle=mine)


# --- emissions ----------------------------------------------------------------

def test_petrol_emissions_come_from_litres_burned(db):
    mine = petrol(db, 6.0)
    theirs = petrol(db, 6.0)

    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-02", "2026-06-14", 1000.0),
    ], theirs, driven_vehicle=mine)

    # 60 L at 2392 g/L — a property of the fuel, not of the engine.
    assert result.alternative_co2_kg == pytest.approx(143.52, abs=0.01)
    assert result.alternative_co2_g_per_km == pytest.approx(143.5, abs=0.1)


def test_diesel_emits_more_per_litre_than_petrol(db):
    """More carbon per litre, which its better economy has to make up for."""
    mine = petrol(db, 6.0)
    same_petrol = petrol(db, 6.0)
    same_diesel = car(db, fuel_type=FuelType.diesel, fuel_consumption_l_per_100km=6.0)
    intervals = [FakeInterval("2026-06-02", "2026-06-14", 1000.0)]

    a = comparison.compare(db, ensure_user(db).id, intervals, same_petrol, driven_vehicle=mine)
    b = comparison.compare(db, ensure_user(db).id, intervals, same_diesel, driven_vehicle=mine)
    assert b.alternative_co2_kg > a.alternative_co2_kg


def test_electric_emissions_depend_on_the_grid(db):
    """An EV has no tailpipe, so its emissions are the power station's and move
    with whatever the grid is running on."""
    from app.config import settings

    mine = petrol(db, 6.0)
    ev = car(db, fuel_type=FuelType.electric, consumption_kwh_per_100km=15.0)
    intervals = [FakeInterval("2026-06-02", "2026-06-14", 1000.0)]

    original = settings.grid_co2_g_per_kwh
    try:
        settings.grid_co2_g_per_kwh = 100.0
        low = comparison.compare(db, ensure_user(db).id, intervals, ev, driven_vehicle=mine)
        settings.grid_co2_g_per_kwh = 400.0
        high = comparison.compare(db, ensure_user(db).id, intervals, ev, driven_vehicle=mine)
    finally:
        settings.grid_co2_g_per_kwh = original

    assert low.alternative_co2_kg == pytest.approx(15.0)     # 150 kWh at 100 g
    assert high.alternative_co2_kg == pytest.approx(60.0)    # at 400 g
    assert high.grid_co2_g_per_kwh == 400.0


def test_emissions_are_reported_without_a_price(db):
    """Cost needs a price; CO2 does not, so a missing price must not take the
    emissions figure down with it."""
    mine = petrol(db, 6.0)
    theirs = petrol(db, 6.0)

    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-02", "2026-06-14", 100.0),
    ], theirs, driven_vehicle=mine)

    assert result.alternative_cost == 0.0 and result.unpriced_intervals == 1
    assert result.alternative_co2_kg > 0


# --- weighing the entered figure against the achieved one ---------------------
#
# The entered figure keeps both cars comparable; the measured one describes
# your actual driving. Which matters is a judgement, so it is a control rather
# than a decision made here.

def test_by_default_nothing_is_measured_in(db):
    mine = petrol(db, 7.0)
    theirs = petrol(db, 7.0)
    intervals = [FakeInterval("2026-06-01", "2026-06-20", 500.0, cost=90.0, litres_added=45.0)]

    result = comparison.compare(db, ensure_user(db).id, intervals, theirs,
                                driven_vehicle=mine, measured_consumption=9.0)

    assert result.your_basis == 7.0
    assert result.measured_weight == 0.0
    assert result.saving == 0.0          # still strictly like-for-like


@pytest.mark.parametrize("weight,expected", [(0.0, 7.0), (0.5, 8.0), (1.0, 9.0)])
def test_the_slider_moves_between_the_two(db, weight, expected):
    mine = petrol(db, 7.0)
    theirs = petrol(db, 7.0)
    intervals = [FakeInterval("2026-06-01", "2026-06-20", 500.0, cost=90.0, litres_added=45.0)]

    result = comparison.compare(db, ensure_user(db).id, intervals, theirs,
                                driven_vehicle=mine, measured_consumption=9.0,
                                measured_weight=weight)
    assert result.your_basis == expected


def test_both_ends_are_reported_so_the_control_can_be_labelled(db):
    mine = petrol(db, 7.0)
    theirs = petrol(db, 6.0)
    intervals = [FakeInterval("2026-06-01", "2026-06-20", 500.0, cost=90.0, litres_added=45.0)]

    result = comparison.compare(db, ensure_user(db).id, intervals, theirs,
                                driven_vehicle=mine, measured_consumption=9.0,
                                measured_weight=0.25)

    assert result.your_basis_quoted == 7.0
    assert result.your_basis_measured == 9.0
    assert result.your_basis == 7.5
    assert result.measured_weight == 0.25


def test_with_nothing_measured_the_weight_is_inert(db):
    """A car with too little logged to derive a figure keeps the entered one,
    rather than the slider quietly doing nothing while claiming otherwise."""
    mine = petrol(db, 7.0)
    theirs = petrol(db, 7.0)

    result = comparison.compare(db, ensure_user(db).id, [
        FakeInterval("2026-06-01", "2026-06-20", 500.0, cost=90.0, litres_added=45.0),
    ], theirs, driven_vehicle=mine, measured_consumption=None, measured_weight=1.0)

    assert result.your_basis == 7.0
    assert result.your_basis_measured is None
    assert result.measured_weight == 0.0


def test_measuring_in_changes_cost_and_co2_together(db):
    mine = petrol(db, 7.0)
    theirs = petrol(db, 7.0)
    intervals = [FakeInterval("2026-06-01", "2026-06-20", 1000.0, cost=180.0, litres_added=90.0)]

    typed = comparison.compare(db, ensure_user(db).id, intervals, theirs,
                               driven_vehicle=mine, measured_consumption=9.0)
    real = comparison.compare(db, ensure_user(db).id, intervals, theirs,
                              driven_vehicle=mine, measured_consumption=9.0,
                              measured_weight=1.0)

    assert typed.saving == 0.0
    # Your car now burns 90 L against its 70, so the other looks better by both
    # measures at once — and the page has to say the two are no longer alike.
    assert real.saving < 0 and real.co2_saving_kg < 0
    assert real.actual_co2_kg > typed.actual_co2_kg


# --- comparing cars with no history between them ------------------------------

def test_two_cars_can_be_compared_over_a_plain_distance(db):
    """Neither needs a log. Two cars being weighed up have no history between
    them, and how far is the only missing piece."""
    a = petrol(db, 6.0, make="Audi", model="A4")
    b = petrol(db, 8.0, make="Audi", model="A6")

    result = comparison.compare(db, ensure_user(db).id,
                                comparison.over_distance(10_000), b, driven_vehicle=a,
                                fallback_price_per_litre=1.80)

    assert result.distance_km == 10_000
    assert result.your_quantity == pytest.approx(600.0)     # 6.0 over 10,000 km
    assert result.quantity == pytest.approx(800.0)
    assert result.saving == pytest.approx(360.0)            # 200 L at 1.80
    assert result.co2_saving_kg == pytest.approx(478.4, abs=0.1)


def test_a_plain_distance_has_no_spend_behind_it(db):
    """Nothing was actually bought, so there is no receipt to report."""
    a = petrol(db, 6.0)
    b = petrol(db, 6.0)

    result = comparison.compare(db, ensure_user(db).id,
                                comparison.over_distance(10_000), b, driven_vehicle=a,
                                fallback_price_per_litre=1.80)
    assert result.actual_spend == 0.0
    assert result.saving == 0.0


def test_a_plain_distance_is_priced_at_the_chosen_day(db):
    add_price(db, D(2026, 6, 1), 1.50)
    add_price(db, D(2026, 7, 1), 2.00)
    a = petrol(db, 6.0)
    b = petrol(db, 6.0)

    june = comparison.compare(db, ensure_user(db).id,
                              comparison.over_distance(1000, D(2026, 6, 15)), b,
                              driven_vehicle=a)
    july = comparison.compare(db, ensure_user(db).id,
                              comparison.over_distance(1000, D(2026, 7, 15)), b,
                              driven_vehicle=a)

    assert june.intervals[0].unit_price == pytest.approx(1.50)
    assert july.intervals[0].unit_price == pytest.approx(2.00)


# --- carrying the real-world gap across ---------------------------------------
#
# Moving your car towards what it actually achieves leaves the other on its
# brochure figure, which flatters it. Lifting both by the same proportion keeps
# them comparable while describing real driving rather than a test cycle.

def test_lifting_both_keeps_identical_cars_identical(db):
    """The property that makes this safe, and the one moving your side alone
    destroys."""
    mine = petrol(db, 7.0)
    theirs = petrol(db, 7.0)
    intervals = [FakeInterval("2026-06-01", "2026-06-20", 500.0, cost=90.0, litres_added=45.0)]

    result = comparison.compare(db, ensure_user(db).id, intervals, theirs,
                                driven_vehicle=mine, measured_consumption=9.0,
                                measured_weight=1.0, apply_gap_to_alternative=True)

    assert result.your_basis == 9.0 and result.basis == 9.0
    assert result.saving == 0.0 and result.co2_saving_kg == 0.0


def test_the_gap_is_a_proportion_not_a_shift(db):
    """A car quoted a quarter thriftier stays a quarter thriftier."""
    mine = petrol(db, 8.0)
    theirs = petrol(db, 6.0)
    intervals = [FakeInterval("2026-06-01", "2026-06-20", 1000.0, cost=160.0, litres_added=80.0)]

    result = comparison.compare(db, ensure_user(db).id, intervals, theirs,
                                driven_vehicle=mine, measured_consumption=10.0,
                                measured_weight=1.0, apply_gap_to_alternative=True)

    assert result.real_world_gap == pytest.approx(1.25)     # 10.0 against 8.0
    assert result.basis == pytest.approx(7.5)               # 6.0 lifted by a quarter
    assert result.basis / result.your_basis == pytest.approx(6.0 / 8.0)


def test_without_the_lift_the_other_car_keeps_its_brochure_figure(db):
    mine = petrol(db, 7.0)
    theirs = petrol(db, 7.0)
    intervals = [FakeInterval("2026-06-01", "2026-06-20", 500.0, cost=90.0, litres_added=45.0)]

    result = comparison.compare(db, ensure_user(db).id, intervals, theirs,
                                driven_vehicle=mine, measured_consumption=9.0,
                                measured_weight=1.0)

    assert result.basis == 7.0 and result.gap_applied is False
    assert result.saving < 0            # yours looks worse, as it should


def test_the_lift_does_nothing_at_the_entered_figure(db):
    """With the slider at zero there is no gap to carry across."""
    mine = petrol(db, 7.0)
    theirs = petrol(db, 6.0)
    intervals = [FakeInterval("2026-06-01", "2026-06-20", 500.0, cost=90.0, litres_added=45.0)]

    result = comparison.compare(db, ensure_user(db).id, intervals, theirs,
                                driven_vehicle=mine, measured_consumption=9.0,
                                apply_gap_to_alternative=True)

    assert result.basis == 6.0
    assert result.gap_applied is False and result.real_world_gap is None


def test_a_car_can_be_compared_with_itself(db):
    """Not a mistake to catch. At the entered figure it reads zero, and with
    the slider moved it weighs what the car achieves against what it claims."""
    mine = petrol(db, 7.0)
    intervals = [FakeInterval("2026-06-01", "2026-06-20", 1000.0, cost=180.0, litres_added=90.0)]

    flat = comparison.compare(db, ensure_user(db).id, intervals, mine, driven_vehicle=mine)
    assert flat.saving == 0.0 and flat.co2_saving_kg == 0.0

    real = comparison.compare(db, ensure_user(db).id, intervals, mine, driven_vehicle=mine,
                              measured_consumption=9.0, measured_weight=1.0)
    assert real.your_basis == 9.0 and real.basis == 7.0
    # What the brochure understates by, in money and carbon.
    assert real.saving < 0 and real.co2_saving_kg < 0


def test_your_car_is_priced_even_with_no_receipt_and_a_different_fuel(db):
    """Over a distance you pick there is no receipt, and falling back to the
    *other* car's fuel priced yours at nothing — an EV against a petrol car
    reported the EV as free."""
    add_price(db, D(2026, 6, 1), 1.80)
    user = ensure_user(db)
    add_tariff(db, user.id, D(2026, 1, 1), [("Flat", 0, 0, 0.30)])

    ev = car(db, make="Renault", model="R4", fuel_type=FuelType.electric,
             consumption_kwh_per_100km=15.0)
    petrol_car = petrol(db, 6.0)

    result = comparison.compare(db, user.id,
                                comparison.over_distance(1000, D(2026, 6, 15)),
                                petrol_car, driven_vehicle=ev)

    # 150 kWh at 0.30, against 60 L at 1.80.
    assert result.actual_cost == pytest.approx(45.0)
    assert result.alternative_cost == pytest.approx(108.0)
    assert result.saving == pytest.approx(63.0)


def test_the_same_holds_when_the_showroom_car_is_the_electric_one(db):
    add_price(db, D(2026, 6, 1), 1.80)
    user = ensure_user(db)
    add_tariff(db, user.id, D(2026, 1, 1), [("Flat", 0, 0, 0.30)])

    mine = petrol(db, 6.0)
    ev = car(db, fuel_type=FuelType.electric, consumption_kwh_per_100km=15.0)

    result = comparison.compare(db, user.id,
                                comparison.over_distance(1000, D(2026, 6, 15)),
                                ev, driven_vehicle=mine)
    assert result.actual_cost == pytest.approx(108.0)
    assert result.alternative_cost == pytest.approx(45.0)
