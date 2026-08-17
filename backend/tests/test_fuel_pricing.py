"""Which fuel price applies to a given date and place."""
import datetime

import pytest

from app.models import FuelPrice, FuelKind, PriceSource
from app.services import fuel_pricing


def add_price(db, day, price, region="", source=PriceSource.eu_oil_bulletin, country="IE"):
    db.add(
        FuelPrice(
            date=day, country=country, region=region, fuel_kind=FuelKind.petrol_95,
            price_per_litre=price, currency="EUR", source=source,
        )
    )
    db.commit()


D = datetime.date


def test_returns_none_when_nothing_ingested(db):
    assert fuel_pricing.price_on(db, D(2026, 7, 20)) is None


def test_uses_most_recent_price_on_or_before_the_date(db):
    """The bulletin is weekly, so mid-week driving is priced from earlier that
    week — never from a later week that hadn't happened yet."""
    add_price(db, D(2026, 7, 13), 1.71)
    add_price(db, D(2026, 7, 20), 1.72)
    add_price(db, D(2026, 7, 27), 1.76)

    q = fuel_pricing.price_on(db, D(2026, 7, 23))
    assert q.price_per_litre == pytest.approx(1.72)
    assert q.as_of == D(2026, 7, 20)
    assert q.staleness_days == 3


def test_exact_date_match_has_zero_staleness(db):
    add_price(db, D(2026, 7, 20), 1.72)
    q = fuel_pricing.price_on(db, D(2026, 7, 20))
    assert q.staleness_days == 0


def test_no_price_before_the_date_returns_none(db):
    add_price(db, D(2026, 7, 20), 1.72)
    assert fuel_pricing.price_on(db, D(2026, 7, 1)) is None


def test_manual_price_beats_the_feed(db):
    add_price(db, D(2026, 7, 20), 1.72, source=PriceSource.eu_oil_bulletin)
    add_price(db, D(2026, 7, 20), 1.65, source=PriceSource.manual)

    q = fuel_pricing.price_on(db, D(2026, 7, 20))
    assert q.price_per_litre == pytest.approx(1.65)
    assert q.source == PriceSource.manual
    assert q.is_estimate is False


def test_manual_national_beats_feed_even_when_older(db):
    """What you recorded yourself is treated as better evidence than an average."""
    add_price(db, D(2026, 7, 1), 1.60, source=PriceSource.manual)
    add_price(db, D(2026, 7, 20), 1.72, source=PriceSource.eu_oil_bulletin)

    q = fuel_pricing.price_on(db, D(2026, 7, 25))
    assert q.source == PriceSource.manual
    assert q.price_per_litre == pytest.approx(1.60)


def test_regional_manual_price_beats_national_manual(db):
    add_price(db, D(2026, 7, 20), 1.65, source=PriceSource.manual)
    add_price(db, D(2026, 7, 20), 1.61, region="Dublin", source=PriceSource.manual)

    q = fuel_pricing.price_on(db, D(2026, 7, 20), region="Dublin")
    assert q.price_per_litre == pytest.approx(1.61)
    assert q.region == "Dublin"


def test_falls_back_to_national_when_region_unknown(db):
    add_price(db, D(2026, 7, 20), 1.72)
    q = fuel_pricing.price_on(db, D(2026, 7, 20), region="Galway")
    assert q.price_per_litre == pytest.approx(1.72)
    assert q.region == ""


def test_country_is_respected(db):
    add_price(db, D(2026, 7, 20), 1.72, country="IE")
    add_price(db, D(2026, 7, 20), 1.85, country="FR")

    assert fuel_pricing.price_on(db, D(2026, 7, 20), country="FR").price_per_litre == pytest.approx(1.85)


def test_fuel_kind_is_respected(db):
    db.add(FuelPrice(date=D(2026, 7, 20), country="IE", region="", fuel_kind=FuelKind.diesel,
                     price_per_litre=1.69, currency="EUR", source=PriceSource.eu_oil_bulletin))
    db.commit()
    assert fuel_pricing.price_on(db, D(2026, 7, 20), fuel_kind=FuelKind.petrol_95) is None
    assert fuel_pricing.price_on(db, D(2026, 7, 20), fuel_kind=FuelKind.diesel) is not None
