"""Choosing which fuel price applies to a given date and place.

Precedence, most specific first:
  1. a price you entered yourself for that exact region
  2. a price you entered yourself for the country
  3. the Oil Bulletin figure for that region (if a regional feed ever exists)
  4. the Oil Bulletin national average

Within a tier the most recent price *on or before* the target date wins — the
bulletin is weekly, so a given day is almost always priced from earlier that
week rather than from an exact date match.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.fuel_price import FuelPrice, FuelKind, PriceSource


@dataclass
class PriceQuote:
    price_per_litre: float
    as_of: datetime.date
    source: PriceSource
    region: str
    """Days between the price's date and the date asked for — 0 is an exact hit."""
    staleness_days: int

    @property
    def is_estimate(self) -> bool:
        return self.source == PriceSource.eu_oil_bulletin


def price_on(
    db: Session,
    day: datetime.date,
    country: str = "IE",
    region: str = "",
    fuel_kind: FuelKind = FuelKind.petrol_95,
) -> PriceQuote | None:
    """Best available price for `day`, or None if nothing has been ingested."""
    tiers: list[tuple[PriceSource, str]] = []
    if region:
        tiers.append((PriceSource.manual, region))
    tiers.append((PriceSource.manual, ""))
    if region:
        tiers.append((PriceSource.eu_oil_bulletin, region))
    tiers.append((PriceSource.eu_oil_bulletin, ""))

    for source, reg in tiers:
        row = db.scalars(
            select(FuelPrice)
            .where(
                FuelPrice.country == country,
                FuelPrice.region == reg,
                FuelPrice.fuel_kind == fuel_kind,
                FuelPrice.source == source,
                FuelPrice.date <= day,
            )
            .order_by(FuelPrice.date.desc())
            .limit(1)
        ).first()
        if row:
            return PriceQuote(
                price_per_litre=row.price_per_litre,
                as_of=row.date,
                source=row.source,
                region=row.region,
                staleness_days=(day - row.date).days,
            )

    return None
