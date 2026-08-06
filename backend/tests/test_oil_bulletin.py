"""Tests for the EU Oil Bulletin parser.

The workbook here is synthesised to match the real file's layout (verified by
inspecting the published 4.4 MB history file), so these run offline and still
catch a layout change if the Commission alters the format.
"""
import datetime
import io

import openpyxl
import pytest

from app.models import FuelPrice, FuelKind, PriceSource
from app.services import oil_bulletin


def build_workbook(rows=None, headers=None) -> bytes:
    """Mimic 'Prices with taxes': header row, fuel-name row, unit row, then data."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = oil_bulletin.SHEET

    headers = headers or [
        "Consumer prices",
        "CTR",
        "EU_price_with_tax_euro95",
        "EU_price_with_tax_diesel",
        "CTR",
        "IE_price_with_tax_euro95",
        "IE_price_with_tax_diesel",
        "CTR",
        "PL_exchange_rate",
        "PL_price_with_tax_euro95",
    ]
    ws.append(headers)
    ws.append([None, None, "Euro-super 95", "Gas oil", None, "Euro-super 95", "Gas oil"])
    ws.append(["Date", None, "1000 l", "1000 l", None, "1000 l", "1000 l"])

    rows = rows or [
        (datetime.datetime(2026, 7, 27), "EU_", 1941.07, 2011.32, "IE_", 1757.70, 1751.70, "PL_", 4.3, 6200.0),
        (datetime.datetime(2026, 7, 20), "EU_", 1908.61, 1927.77, "IE_", 1720.20, 1695.00, "PL_", 4.3, 6180.0),
    ]
    for r in rows:
        ws.append(list(r))

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parses_prices_as_euros_per_litre():
    parsed = oil_bulletin.parse(build_workbook())
    ie = {(d, f): p for d, c, f, p in parsed if c == "IE"}

    # The sheet quotes per 1000 litres, so 1720.20 is €1.7202/l.
    assert ie[(datetime.date(2026, 7, 20), FuelKind.petrol_95)] == pytest.approx(1.7202)
    assert ie[(datetime.date(2026, 7, 20), FuelKind.diesel)] == pytest.approx(1.695)


def test_skips_eu_aggregates():
    """'EU' and 'EUR' are averages, not countries — treating them as one would
    invent a country whose prices are nobody's."""
    countries = {c for _, c, _, _ in oil_bulletin.parse(build_workbook())}
    assert "IE" in countries
    assert "EU" not in countries
    assert "EUR" not in countries


def test_skips_non_euro_countries():
    """Their figures are in local currency; converting needs historical FX."""
    countries = {c for _, c, _, _ in oil_bulletin.parse(build_workbook())}
    assert "PL" not in countries


def test_ignores_exchange_rate_columns():
    parsed = oil_bulletin.parse(build_workbook())
    # 4.3 is an FX rate, not a price; it must not appear as €0.0043/l.
    assert all(p > 0.5 for _, _, _, p in parsed)


def test_country_filter():
    parsed = oil_bulletin.parse(build_workbook(), countries={"IE"})
    assert {c for _, c, _, _ in parsed} == {"IE"}


def test_blank_and_zero_cells_are_skipped():
    rows = [
        (datetime.datetime(2026, 7, 20), "EU_", 1908.61, 1927.77, "IE_", None, 0),
    ]
    parsed = oil_bulletin.parse(build_workbook(rows=rows))
    assert [p for _, c, _, p in parsed if c == "IE"] == []


def test_non_date_rows_are_skipped():
    rows = [
        ("some footnote", None, None, None, "IE_", 1720.20, 1695.00),
        (datetime.datetime(2026, 7, 20), "EU_", 1908.61, 1927.77, "IE_", 1720.20, 1695.00),
    ]
    parsed = oil_bulletin.parse(build_workbook(rows=rows))
    assert len([1 for _, c, _, _ in parsed if c == "IE"]) == 2  # petrol + diesel, one date


def test_layout_change_raises_rather_than_silently_returning_nothing():
    """If the Commission renames the columns we want a loud failure, not an
    empty import that looks like success."""
    bad = build_workbook(headers=["Date", "CTR", "IE_something_else", "IE_another"])
    with pytest.raises(ValueError, match="no matching price columns"):
        oil_bulletin.parse(bad)


def test_missing_sheet_raises():
    wb = openpyxl.Workbook()
    wb.active.title = "Something Else"
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(ValueError, match="expected sheet"):
        oil_bulletin.parse(buf.getvalue())


def test_ingest_inserts_then_is_idempotent(db):
    data = build_workbook()

    first = oil_bulletin.ingest(db, data=data, countries={"IE"})
    assert first.inserted == 4  # 2 dates x 2 fuels
    assert first.updated == 0
    assert first.countries == ["IE"]
    assert first.earliest == datetime.date(2026, 7, 20)
    assert first.latest == datetime.date(2026, 7, 27)

    second = oil_bulletin.ingest(db, data=data, countries={"IE"})
    assert second.inserted == 0
    assert second.updated == 0
    assert db.query(FuelPrice).count() == 4


def test_ingest_updates_a_revised_price(db):
    oil_bulletin.ingest(db, data=build_workbook(), countries={"IE"})

    revised = build_workbook(rows=[
        (datetime.datetime(2026, 7, 20), "EU_", 1908.61, 1927.77, "IE_", 1799.00, 1695.00),
    ])
    result = oil_bulletin.ingest(db, data=revised, countries={"IE"})

    assert result.updated == 1
    row = (
        db.query(FuelPrice)
        .filter_by(date=datetime.date(2026, 7, 20), fuel_kind=FuelKind.petrol_95)
        .one()
    )
    assert row.price_per_litre == pytest.approx(1.799)


def test_ingest_never_overwrites_manual_prices(db):
    """A re-import must not clobber a price the user entered themselves."""
    db.add(
        FuelPrice(
            date=datetime.date(2026, 7, 20), country="IE", region="",
            fuel_kind=FuelKind.petrol_95, price_per_litre=1.65,
            currency="EUR", source=PriceSource.manual,
        )
    )
    db.commit()

    oil_bulletin.ingest(db, data=build_workbook(), countries={"IE"})

    manual = db.query(FuelPrice).filter_by(source=PriceSource.manual).one()
    assert manual.price_per_litre == 1.65
    # and the feed price exists alongside it
    feed = db.query(FuelPrice).filter_by(
        source=PriceSource.eu_oil_bulletin,
        date=datetime.date(2026, 7, 20),
        fuel_kind=FuelKind.petrol_95,
    ).one()
    assert feed.price_per_litre == pytest.approx(1.7202)
