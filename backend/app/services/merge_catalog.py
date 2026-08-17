"""Complement EEA registration rows with EV detail from evdb.

The two sources answer different halves of the question:

  * EEA knows what is actually registered in Ireland, and covers petrol and
    diesel — but records no battery capacity or WLTP range.
  * evdb has battery, usable capacity and WLTP range — but only for EVs, with
    no notion of which market a car sold in.

So for an electric EEA row we look up the matching evdb entry and copy across
the fields EEA lacks. Nothing is overwritten: only empty fields are filled, and
`enriched_from` records where the extra data came from.

Matching is on normalised make and model, because the two sources name things
differently: EEA says "RENAULT" / "RENAULT 4 E-TECH ELECTRIC" where evdb says
"Renault" / "4 E-Tech". Where several evdb variants match, motor power breaks
the tie — that is what distinguishes a 40 kWh car from a 52 kWh one.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import CatalogVehicle, CatalogSource
from app.models.vehicle import FuelType

# The naming rules live with the dropdown grouping that also depends on them,
# so the two can never drift apart. Re-exported: this module's callers and
# tests have used these names since before that split.
from app.services.catalog_naming import (  # noqa: F401
    NOISE,
    make_key,
    model_key,
    normalise,
)

# Copied only when the target field is empty.
FILLABLE = (
    "battery_capacity_kwh",
    "battery_usable_kwh",
    "onboard_charger_kw",
    "dc_charge_power_kw",
    "wltp_range_km",
    "consumption_wltp_kwh_100km",
    "consumption_real_world_kwh_100km",
    "zero_to_100_seconds",
    "top_speed_kmh",
    "body_style",
    "image_url",
)

@dataclass
class MergeResult:
    considered: int
    matched: int
    enriched: int
    unmatched: list[str]


def _score(evdb_row: CatalogVehicle, target: CatalogVehicle) -> tuple[int, float]:
    """Rank candidate evdb rows: prefer similar power, then more complete data."""
    power_gap = (
        abs((evdb_row.horsepower or 0) - (target.horsepower or 0))
        if target.horsepower and evdb_row.horsepower
        else 999
    )
    completeness = sum(getattr(evdb_row, f) is not None for f in FILLABLE)
    return (power_gap, -completeness)


def enrich_from_evdb(db: Session, dry_run: bool = False) -> MergeResult:
    evdb_rows = db.scalars(
        select(CatalogVehicle).where(CatalogVehicle.source == CatalogSource.evdb)
    ).all()

    index: dict[tuple[str, str], list[CatalogVehicle]] = {}
    for row in evdb_rows:
        index.setdefault((make_key(row.make), model_key(row.make, row.model)), []).append(row)

    targets = db.scalars(
        select(CatalogVehicle).where(
            CatalogVehicle.source == CatalogSource.eea,
            CatalogVehicle.fuel_type == FuelType.electric,
        )
    ).all()

    matched = enriched = 0
    unmatched: list[str] = []

    for target in targets:
        key = (make_key(target.make), model_key(target.make, target.model))
        candidates = index.get(key)

        if not candidates:
            # Fall back to a prefix match: "5" should still find "5 E-Tech".
            candidates = [
                r
                for (mk, mdl), rows in index.items()
                if mk == key[0] and key[1] and (mdl.startswith(key[1]) or key[1].startswith(mdl))
                for r in rows
            ]

        if not candidates:
            unmatched.append(f"{target.make} {target.model}")
            continue

        matched += 1
        best = sorted(candidates, key=lambda r: _score(r, target))[0]

        changed = False
        for field in FILLABLE:
            if getattr(target, field) is None and getattr(best, field) is not None:
                if not dry_run:
                    setattr(target, field, getattr(best, field))
                changed = True

        if changed:
            enriched += 1
            if not dry_run:
                target.enriched_from = best.id

    if not dry_run:
        db.commit()

    return MergeResult(
        considered=len(targets),
        matched=matched,
        enriched=enriched,
        unmatched=sorted(set(unmatched)),
    )
