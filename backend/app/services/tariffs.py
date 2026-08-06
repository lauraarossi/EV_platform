"""Electricity tariff versioning and rate lookup."""

from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tariff import ElectricityTariff, TariffRate


def tariff_on(db: Session, day: datetime.date) -> ElectricityTariff | None:
    """The tariff version in force on `day`."""
    return db.scalars(
        select(ElectricityTariff)
        .where(
            ElectricityTariff.effective_from <= day,
            (ElectricityTariff.effective_to.is_(None)) | (ElectricityTariff.effective_to >= day),
        )
        .order_by(ElectricityTariff.effective_from.desc())
        .limit(1)
    ).first()


def band_covers(rate: TariffRate, at: datetime.time) -> bool:
    """Whether a rate band covers a time, allowing bands that wrap midnight."""
    start, end = rate.start_time, rate.end_time
    if start == end:
        return True  # a single band covering the whole day
    if start < end:
        return start <= at < end
    # wraps midnight, e.g. 23:00 -> 08:00
    return at >= start or at < end


def rate_for(
    db: Session, day: datetime.date, at: datetime.time | None
) -> tuple[ElectricityTariff, TariffRate] | None:
    """The tariff and price band applying at a given date and time."""
    tariff = tariff_on(db, day)
    if not tariff or not tariff.rates:
        return None

    if at is None:
        # No time recorded: fall back to the cheapest band rather than guessing,
        # and let the caller present it as an estimate.
        return tariff, min(tariff.rates, key=lambda r: r.price_per_kwh)

    for rate in tariff.rates:
        if band_covers(rate, at):
            return tariff, rate
    return None


def close_open_versions(db: Session, new_from: datetime.date, exclude_id: int | None = None) -> None:
    """Close any still-open tariff that starts before a newly added one.

    Versions are meant to tile the timeline without overlapping, so adding a
    version starting today ends yesterday's.
    """
    stmt = select(ElectricityTariff).where(
        ElectricityTariff.effective_to.is_(None),
        ElectricityTariff.effective_from < new_from,
    )
    if exclude_id is not None:
        stmt = stmt.where(ElectricityTariff.id != exclude_id)

    for tariff in db.scalars(stmt):
        tariff.effective_to = new_from - datetime.timedelta(days=1)
