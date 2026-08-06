"""Ingest the European Commission's Weekly Oil Bulletin.

The Commission publishes consumer pump prices (inclusive of duties and taxes)
for every EU member state, weekly, back to 2005. It is the official source that
most commercial fuel-price APIs resell.

Format notes, established by inspecting the actual file:
  * Sheet "Prices with taxes".
  * Row 1 holds column headers of the form ``{CC}_price_with_tax_{fuel}``,
    e.g. ``IE_price_with_tax_euro95``. Non-euro countries additionally have a
    ``{CC}_exchange_rate`` column, which we ignore.
  * Rows 2 and 3 are fuel names and units; data starts at row 4.
  * Column 0 is the week's date.
  * **Prices are per 1000 litres**, so they are divided by 1000 here.

Only euro-denominated countries are ingested: for the others the sheet reports
local currency, and converting historical prices correctly would need the
matching historical FX rate.
"""

from __future__ import annotations

import datetime
import io
import re
from dataclasses import dataclass

import httpx
import openpyxl
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.fuel_price import FuelPrice, FuelKind, PriceSource

HISTORY_URL = (
    "https://energy.ec.europa.eu/document/download/"
    "906e60ca-8b6a-44e7-8589-652854d2fd3f_en"
    "?filename=Weekly_Oil_Bulletin_Prices_History_maticni_4web.xlsx"
)

SHEET = "Prices with taxes"
HEADER_RE = re.compile(r"^([A-Z]{2,3})_price_with_tax_(\w+)$")

# The bulletin's fuel keys we care about, mapped to our own enum.
FUEL_MAP = {"euro95": FuelKind.petrol_95, "diesel": FuelKind.diesel}

# Aggregates rather than countries; skipped so "IE" means Ireland only.
AGGREGATES = {"EU", "EUR"}

# Countries whose bulletin figures are already in euro.
EURO_COUNTRIES = {
    "AT", "BE", "CY", "DE", "EE", "ES", "FI", "FR", "GR", "HR", "IE",
    "IT", "LT", "LU", "LV", "MT", "NL", "PT", "SI", "SK",
}

LITRES_PER_UNIT = 1000.0


@dataclass
class IngestResult:
    fetched_rows: int
    inserted: int
    updated: int
    countries: list[str]
    earliest: datetime.date | None
    latest: datetime.date | None


def fetch_workbook_bytes(url: str = HISTORY_URL, timeout: float = 120.0) -> bytes:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.content


def parse(
    data: bytes, countries: set[str] | None = None
) -> list[tuple[datetime.date, str, FuelKind, float]]:
    """Return (date, country, fuel, price_per_litre) tuples from the workbook."""
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    if SHEET not in wb.sheetnames:
        raise ValueError(f"expected sheet {SHEET!r}, found {wb.sheetnames}")
    ws = wb[SHEET]

    rows = ws.iter_rows(values_only=True)
    header = next(rows)

    wanted: dict[int, tuple[str, FuelKind]] = {}
    for idx, cell in enumerate(header):
        m = HEADER_RE.match(str(cell or ""))
        if not m:
            continue
        country, fuel_key = m.group(1), m.group(2)
        if country in AGGREGATES or fuel_key not in FUEL_MAP:
            continue
        if country not in EURO_COUNTRIES:
            continue
        if countries and country not in countries:
            continue
        wanted[idx] = (country, FUEL_MAP[fuel_key])

    if not wanted:
        raise ValueError("no matching price columns found — file layout may have changed")

    next(rows, None)  # fuel names
    next(rows, None)  # units

    out: list[tuple[datetime.date, str, FuelKind, float]] = []
    for row in rows:
        raw_date = row[0] if row else None
        if isinstance(raw_date, datetime.datetime):
            day = raw_date.date()
        elif isinstance(raw_date, datetime.date):
            day = raw_date
        else:
            continue

        for idx, (country, fuel) in wanted.items():
            if idx >= len(row):
                continue
            value = row[idx]
            if not isinstance(value, (int, float)) or value <= 0:
                continue  # blanks and placeholder zeros are simply absent weeks
            out.append((day, country, fuel, round(value / LITRES_PER_UNIT, 5)))

    return out


def ingest(
    db: Session,
    data: bytes | None = None,
    countries: set[str] | None = None,
) -> IngestResult:
    """Parse the bulletin and upsert national-average prices.

    Manual prices are stored under a different `source`, so re-running this
    never overwrites anything the user entered themselves.
    """
    if data is None:
        data = fetch_workbook_bytes()

    parsed = parse(data, countries=countries)

    existing = {
        (p.date, p.country, p.fuel_kind): p
        for p in db.scalars(
            select(FuelPrice).where(
                FuelPrice.source == PriceSource.eu_oil_bulletin, FuelPrice.region == ""
            )
        )
    }

    inserted = updated = 0
    for day, country, fuel, price in parsed:
        current = existing.get((day, country, fuel))
        if current is None:
            db.add(
                FuelPrice(
                    date=day,
                    country=country,
                    region="",
                    fuel_kind=fuel,
                    price_per_litre=price,
                    currency="EUR",
                    source=PriceSource.eu_oil_bulletin,
                )
            )
            inserted += 1
        elif current.price_per_litre != price:
            current.price_per_litre = price
            updated += 1

    db.commit()

    dates = [p[0] for p in parsed]
    return IngestResult(
        fetched_rows=len(parsed),
        inserted=inserted,
        updated=updated,
        countries=sorted({p[1] for p in parsed}),
        earliest=min(dates) if dates else None,
        latest=max(dates) if dates else None,
    )
