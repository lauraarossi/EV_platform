"""Import the open EV database (gaia-charge/evdb) into the local catalogue.

The project publishes a SQLite build as a GitHub release asset. Downloading
that rather than querying their API keeps this free of a runtime dependency on
someone else's uptime, and makes the import reproducible.

Data is CC BY-SA 4.0, so each row records its own attribution.

Coverage notes, from inspecting the Feb 2026 release (533 variants, 56 brands):
  * `trim_level` is empty for every row — the trim is inside `variant_name`
    ("Renault 4 E-Tech Electric Techno 52"), so the picker cascades
    make -> model -> variant rather than offering a separate trim step.
  * `ac_onboard_charger_kw` and `dc_charge_power_kw` are empty throughout, so
    charging specs cannot be prefilled.
  * Battery, range, top speed and weight are ~100% populated; power 92%,
    0-100 97%.
  * It is EV-only: petrol comparison cars are not in it.
"""

from __future__ import annotations

import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import CatalogVehicle, CatalogSource
from app.models.vehicle import FuelType, Transmission

RELEASE_API = "https://api.github.com/repos/gaia-charge/evdb/releases/latest"
SOURCE_NAME = "Open EV Database (gaia-charge/evdb)"
SOURCE_URL = "https://github.com/gaia-charge/evdb"
LICENCE = "CC BY-SA 4.0"

KW_TO_HP = 1.35962


@dataclass
class CatalogImportResult:
    release: str | None
    fetched: int
    inserted: int
    updated: int
    makes: int
    models: int


def _latest_asset_url(timeout: float = 60.0) -> tuple[str, str | None]:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        r = client.get(RELEASE_API, headers={"Accept": "application/vnd.github+json"})
        r.raise_for_status()
        payload = r.json()

    for asset in payload.get("assets", []):
        if asset.get("name", "").endswith(".db"):
            return asset["browser_download_url"], payload.get("tag_name")
    raise ValueError("no .db asset found in the latest evdb release")


def download_snapshot(timeout: float = 300.0) -> tuple[bytes, str | None]:
    url, tag = _latest_asset_url()
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.content, tag


def _hp(kw: float | None) -> int | None:
    return round(kw * KW_TO_HP) if kw else None


def read_rows(db_bytes: bytes) -> list[dict]:
    """Pull the joined manufacturer/model/variant rows out of an evdb snapshot."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp.write(db_bytes)
        path = Path(tmp.name)

    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT
                    v.id                                AS id,
                    m.brand                             AS make,
                    m.name                              AS model,
                    m.body_style                        AS body_style,
                    m.image_url                         AS image_url,
                    v.variant_name                      AS variant,
                    v.model_year                        AS model_year,
                    v.battery_capacity_kwh              AS battery_capacity_kwh,
                    v.battery_usable_kwh                AS battery_usable_kwh,
                    v.ac_onboard_charger_kw             AS onboard_charger_kw,
                    v.dc_charge_power_kw                AS dc_charge_power_kw,
                    v.range_wltp_km                     AS wltp_range_km,
                    v.consumption_wltp_kwh_100km        AS consumption_wltp_kwh_100km,
                    v.consumption_real_world_kwh_100km  AS consumption_real_world_kwh_100km,
                    v.total_power_kw                    AS total_power_kw,
                    v.acceleration_0_100_sec            AS zero_to_100_seconds,
                    v.top_speed_kph                     AS top_speed_kmh,
                    v.weight_curb_kg                    AS kerb_weight_kg,
                    v.data_quality                      AS data_quality
                FROM vehicle_variants v
                JOIN vehicle_models m ON m.id = v.model_id
                WHERE m.brand IS NOT NULL AND m.brand <> ''
                """
            ).fetchall()
        finally:
            conn.close()
    finally:
        path.unlink(missing_ok=True)

    return [dict(r) for r in rows]


FIELDS = (
    "make model variant model_year body_style image_url data_quality "
    "battery_capacity_kwh battery_usable_kwh onboard_charger_kw dc_charge_power_kw "
    "wltp_range_km consumption_wltp_kwh_100km consumption_real_world_kwh_100km "
    "zero_to_100_seconds top_speed_kmh kerb_weight_kg"
).split()


def to_catalog_values(row: dict) -> dict:
    values = {f: row.get(f) for f in FIELDS}
    values["horsepower"] = _hp(row.get("total_power_kw"))
    values["fuel_type"] = FuelType.electric
    # Effectively every EV in the set is single-speed; the user can override.
    values["transmission"] = Transmission.single_speed
    values["top_speed_kmh"] = int(row["top_speed_kmh"]) if row.get("top_speed_kmh") else None
    values["kerb_weight_kg"] = int(row["kerb_weight_kg"]) if row.get("kerb_weight_kg") else None
    return values


def ingest(db: Session, db_bytes: bytes | None = None) -> CatalogImportResult:
    tag: str | None = None
    if db_bytes is None:
        db_bytes, tag = download_snapshot()

    rows = read_rows(db_bytes)

    existing = {
        c.id: c
        for c in db.scalars(
            select(CatalogVehicle).where(CatalogVehicle.source == CatalogSource.evdb)
        )
    }

    inserted = updated = 0
    for row in rows:
        values = to_catalog_values(row)
        current = existing.get(row["id"])

        if current is None:
            db.add(
                CatalogVehicle(
                    id=row["id"],
                    source=CatalogSource.evdb,
                    source_name=SOURCE_NAME,
                    source_url=SOURCE_URL,
                    licence=LICENCE,
                    **values,
                )
            )
            inserted += 1
        else:
            changed = False
            for key, value in values.items():
                if getattr(current, key) != value:
                    setattr(current, key, value)
                    changed = True
            updated += int(changed)

    db.commit()

    return CatalogImportResult(
        release=tag,
        fetched=len(rows),
        inserted=inserted,
        updated=updated,
        makes=len({r["make"] for r in rows}),
        models=len({(r["make"], r["model"]) for r in rows}),
    )
