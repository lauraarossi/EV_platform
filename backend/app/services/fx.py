"""Exchange rates, so money can be shown in the currency someone actually uses.

Rates come from the European Central Bank's daily reference series, via
Frankfurter — free, no key, and published against the euro, which is what
everything here is already denominated in. The same provenance as the fuel
prices, and the same treatment: the series is stored rather than a single
current figure, because a charge from March should convert at March's rate.

Nothing is converted on write. Amounts stay in the currency they were entered
in, and conversion happens at the edge, for display — the same rule the unit
system follows, and for the same reason: a stored figure that depends on when
it was converted is impossible to reason about later.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.exchange_rate import ExchangeRate

API = "https://api.frankfurter.dev/v1"
SOURCE = "European Central Bank (via Frankfurter)"
BASE = "EUR"

# What the interface offers. Three, deliberately: the euro for here, sterling
# for the North and Britain, the dollar for everywhere that quotes in it.
# Adding more is a line each, but a long list in a dropdown is a cost paid by
# everyone to serve almost nobody.
CURRENCIES: dict[str, str] = {
    "EUR": "€",
    "GBP": "£",
    "USD": "$",
}

QUOTES = [c for c in CURRENCIES if c != BASE]


@dataclass
class FxImportResult:
    fetched: int
    inserted: int
    updated: int
    latest_date: str | None
    currencies: int


def fetch(day: datetime.date | None = None, symbols: list[str] | None = None) -> dict:
    """Rates for one day, or the most recent published day.

    The ECB publishes on working days only, so a weekend request answers with
    Friday's — which is why the response carries its own date rather than the
    one asked for.
    """
    when = day.isoformat() if day else "latest"
    params = {"base": BASE, "symbols": ",".join(symbols or QUOTES)}
    response = httpx.get(f"{API}/{when}", params=params, timeout=30.0)
    response.raise_for_status()
    return response.json()


def ingest(db: Session, day: datetime.date | None = None, data: dict | None = None) -> FxImportResult:
    """Store one day's rates, replacing that day's if it has been revised."""
    payload = data if data is not None else fetch(day)
    rates: dict[str, float] = payload.get("rates") or {}
    if not rates:
        raise ValueError("the rates response carried no rates")

    on = datetime.date.fromisoformat(payload["date"])
    existing = {
        r.quote: r
        for r in db.scalars(
            select(ExchangeRate).where(
                ExchangeRate.date == on, ExchangeRate.base == BASE
            )
        )
    }

    inserted = updated = 0
    for quote, rate in rates.items():
        current = existing.get(quote)
        if current is None:
            db.add(ExchangeRate(date=on, base=BASE, quote=quote, rate=float(rate)))
            inserted += 1
        elif current.rate != float(rate):
            current.rate = float(rate)
            updated += 1

    db.commit()
    return FxImportResult(
        fetched=len(rates),
        inserted=inserted,
        updated=updated,
        latest_date=on.isoformat(),
        currencies=len(rates),
    )


def rate_on(
    db: Session, quote: str, day: datetime.date | None = None
) -> tuple[float, datetime.date] | None:
    """The rate for `quote` on or before `day`, and the day it is actually from.

    Most recent on or before, rather than an exact match: the series has no
    weekends or holidays in it, so an exact-date lookup would miss two days in
    seven.
    """
    quote = quote.upper()
    if quote == BASE:
        return 1.0, day or datetime.date.today()

    stmt = (
        select(ExchangeRate)
        .where(ExchangeRate.base == BASE, ExchangeRate.quote == quote)
        .order_by(ExchangeRate.date.desc())
        .limit(1)
    )
    if day is not None:
        stmt = stmt.where(ExchangeRate.date <= day)

    row = db.scalars(stmt).first()
    return (row.rate, row.date) if row else None


def convert(
    db: Session, amount: float, to: str, day: datetime.date | None = None
) -> float | None:
    """Convert from the base currency. None when no rate is known yet."""
    found = rate_on(db, to, day)
    return round(amount * found[0], 2) if found else None


def latest_rates(db: Session) -> dict[str, float]:
    """The newest rate held for each currency, for the client to convert with."""
    out = {BASE: 1.0}
    for quote in QUOTES:
        found = rate_on(db, quote)
        if found:
            out[quote] = found[0]
    return out
