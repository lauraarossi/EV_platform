"""Electricity tariff versioning and time-band lookup."""
import datetime

import pytest

from app.models import ElectricityTariff, TariffRate
from tests.conftest import ensure_user
from app.schemas.tariff import TariffCreate
from app.services import tariffs as svc

D = datetime.date
T = datetime.time


def make_tariff(db, name, effective_from, effective_to=None, bands=None):
    bands = bands or [("Day", T(8, 0), T(23, 0), 0.35), ("Night", T(23, 0), T(8, 0), 0.17)]
    t = ElectricityTariff(
        name=name, effective_from=effective_from, effective_to=effective_to, currency="EUR",
        user_id=ensure_user(db).id,
    )
    t.rates = [
        TariffRate(name=n, start_time=s, end_time=e, price_per_kwh=p) for n, s, e, p in bands
    ]
    db.add(t)
    db.commit()
    return t


# --- band matching ------------------------------------------------------------

@pytest.mark.parametrize(
    "at,expected",
    [
        (T(9, 0), "Day"),
        (T(22, 59), "Day"),
        (T(23, 0), "Night"),   # band start is inclusive
        (T(2, 0), "Night"),    # after midnight, still the night band
        (T(7, 59), "Night"),
        (T(8, 0), "Day"),      # band end is exclusive
    ],
)
def test_night_band_wraps_midnight(db, at, expected):
    make_tariff(db, "Night Saver", D(2026, 1, 1))
    _, rate = svc.rate_for(db, ensure_user(db).id, D(2026, 6, 1), at)
    assert rate.name == expected


def test_flat_tariff_covers_every_hour(db):
    make_tariff(db, "Flat", D(2026, 1, 1), bands=[("Standard", T(0, 0), T(0, 0), 0.30)])
    for at in (T(0, 0), T(12, 0), T(23, 59)):
        _, rate = svc.rate_for(db, ensure_user(db).id, D(2026, 6, 1), at)
        assert rate.price_per_kwh == pytest.approx(0.30)


def test_missing_time_assumes_cheapest_band(db):
    """Better to under-assume than to invent a peak-rate charge."""
    make_tariff(db, "Night Saver", D(2026, 1, 1))
    _, rate = svc.rate_for(db, ensure_user(db).id, D(2026, 6, 1), None)
    assert rate.name == "Night"


# --- versioning ---------------------------------------------------------------

def test_lookup_picks_the_version_in_force(db):
    make_tariff(db, "Old", D(2025, 1, 1), effective_to=D(2025, 12, 31),
                bands=[("Flat", T(0, 0), T(0, 0), 0.28)])
    make_tariff(db, "New", D(2026, 1, 1), bands=[("Flat", T(0, 0), T(0, 0), 0.34)])

    assert svc.tariff_on(db, ensure_user(db).id, D(2025, 6, 1)).name == "Old"
    assert svc.tariff_on(db, ensure_user(db).id, D(2026, 6, 1)).name == "New"


def test_no_tariff_before_the_first_version(db):
    make_tariff(db, "Only", D(2026, 1, 1))
    assert svc.tariff_on(db, ensure_user(db).id, D(2025, 12, 31)) is None
    assert svc.rate_for(db, ensure_user(db).id, D(2025, 12, 31), T(9, 0)) is None


def test_open_ended_version_covers_the_future(db):
    make_tariff(db, "Current", D(2026, 1, 1))
    assert svc.tariff_on(db, ensure_user(db).id, D(2030, 1, 1)).name == "Current"


def test_adding_a_version_closes_the_previous_one(db):
    old = make_tariff(db, "Old", D(2025, 1, 1))
    assert old.effective_to is None

    svc.close_open_versions(db, ensure_user(db).id, D(2026, 1, 1))
    db.commit()

    assert old.effective_to == D(2025, 12, 31)


def test_closing_does_not_touch_the_new_version_itself(db):
    old = make_tariff(db, "Old", D(2025, 1, 1))
    new = make_tariff(db, "New", D(2026, 1, 1))

    svc.close_open_versions(db, ensure_user(db).id, D(2026, 1, 1), exclude_id=new.id)
    db.commit()

    assert old.effective_to == D(2025, 12, 31)
    assert new.effective_to is None


def test_historical_charge_keeps_its_original_rate(db):
    """Changing your tariff must not retroactively reprice old charges."""
    make_tariff(db, "Old", D(2025, 1, 1), effective_to=D(2025, 12, 31),
                bands=[("Flat", T(0, 0), T(0, 0), 0.28)])
    make_tariff(db, "New", D(2026, 1, 1), bands=[("Flat", T(0, 0), T(0, 0), 0.40)])

    _, old_rate = svc.rate_for(db, ensure_user(db).id, D(2025, 6, 1), T(23, 30))
    _, new_rate = svc.rate_for(db, ensure_user(db).id, D(2026, 6, 1), T(23, 30))

    assert old_rate.price_per_kwh == pytest.approx(0.28)
    assert new_rate.price_per_kwh == pytest.approx(0.40)


# --- schema validation --------------------------------------------------------

def test_overlapping_bands_are_rejected():
    with pytest.raises(ValueError, match="overlaps"):
        TariffCreate(
            name="Bad", effective_from=D(2026, 1, 1),
            rates=[
                {"name": "A", "start_time": "08:00", "end_time": "18:00", "price_per_kwh": 0.3},
                {"name": "B", "start_time": "17:00", "end_time": "23:00", "price_per_kwh": 0.4},
            ],
        )


def test_overlap_detected_across_midnight_wrap():
    with pytest.raises(ValueError, match="overlaps"):
        TariffCreate(
            name="Bad", effective_from=D(2026, 1, 1),
            rates=[
                {"name": "Night", "start_time": "23:00", "end_time": "08:00", "price_per_kwh": 0.17},
                {"name": "Early", "start_time": "05:00", "end_time": "09:00", "price_per_kwh": 0.30},
            ],
        )


def test_adjacent_bands_are_allowed():
    t = TariffCreate(
        name="Good", effective_from=D(2026, 1, 1),
        rates=[
            {"name": "Day", "start_time": "08:00", "end_time": "23:00", "price_per_kwh": 0.35},
            {"name": "Night", "start_time": "23:00", "end_time": "08:00", "price_per_kwh": 0.17},
        ],
    )
    assert len(t.rates) == 2


def test_effective_to_before_from_is_rejected():
    with pytest.raises(ValueError, match="effective_to"):
        TariffCreate(
            name="Bad", effective_from=D(2026, 6, 1), effective_to=D(2026, 1, 1),
            rates=[{"name": "Flat", "start_time": "00:00", "end_time": "00:00", "price_per_kwh": 0.3}],
        )


def test_at_least_one_rate_required():
    with pytest.raises(ValueError):
        TariffCreate(name="Bad", effective_from=D(2026, 1, 1), rates=[])
