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


@dataclass
class PricedInterval:
    start_date: str
    end_date: str
    distance_km: float
    litres: float
    price_per_litre: float | None
    petrol_cost: float | None
    price_as_of: str | None
    price_is_estimate: bool


def price_intervals(
    db: Session,
    intervals: list,
    l_per_100km: float,
    country: str = "IE",
    fallback_price: float | None = None,
) -> tuple[list[PricedInterval], float, bool]:
    """Cost each interval of driving at the petrol price that applied *then*.

    Pricing every interval at today's rate would misstate any history longer
    than a few weeks, which is the whole reason for storing the series.

    Returns (priced intervals, total cost, whether any interval fell back).
    """
    priced: list[PricedInterval] = []
    total = 0.0
    used_fallback = False

    for iv in intervals:
        day = datetime.date.fromisoformat(iv.end_date)
        region = iv.location_city or ""
        quote = price_on(db, day, country=country, region=region)

        litres = iv.distance_km / 100.0 * l_per_100km
        unit = quote.price_per_litre if quote else fallback_price
        if quote is None and fallback_price is not None:
            used_fallback = True

        cost = round(litres * unit, 2) if unit is not None else None
        if cost is not None:
            total += cost

        priced.append(
            PricedInterval(
                start_date=iv.start_date,
                end_date=iv.end_date,
                distance_km=iv.distance_km,
                litres=round(litres, 2),
                price_per_litre=unit,
                petrol_cost=cost,
                price_as_of=quote.as_of.isoformat() if quote else None,
                price_is_estimate=quote.is_estimate if quote else True,
            )
        )

    return priced, round(total, 2), used_fallback
