"""Ingest vehicle specs from the EEA CO2 monitoring dataset.

Source: "Monitoring of CO2 emissions from passenger cars, Regulation (EU)
2019/631" — every new car registered in the EU, published by the European
Environment Agency and queryable over SQL at discodata.eea.europa.eu.

Why this alongside evdb: evdb is EV-only, so petrol and diesel comparison cars
had no source at all. This one covers every fuel type and, because it is
registration data, it describes cars actually sold in a given country.

Column names in the source are terse; the mapping is:
    Mk          make                    Ec (cm3)   engine capacity
    Cn          commercial name         Ep (KW)    engine power
    Ft          fuel type               Fc         fuel consumption l/100km
    MS          member state            M (kg)     mass in running order
    Z (Wh/km)   electric consumption    Ewltp      CO2 g/km

Known limits, established by querying the live endpoint:
  * Only the current registration year is exposed over SQL; older cars (a 2017
    Audi A4, say) are not present. Historical years exist only as bulk files.
  * There is no trim name — `Cn` is the commercial name ("CAPTUR"), not the
    marketing trim ("Techno TCe 150"). Engine variants are distinguished by
    capacity and power instead.
  * No battery capacity or WLTP range for EVs; that gap is filled from evdb by
    `merge_catalog.enrich_from_evdb`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import CatalogVehicle, CatalogSource
from app.models.vehicle import FuelType, Transmission

SQL_ENDPOINT = "https://discodata.eea.europa.eu/sql"
TABLE = "[CO2Emission].[latest].[co2cars_2025Pv31]"
SOURCE_NAME = "EEA CO2 monitoring (Regulation EU 2019/631)"
SOURCE_URL = "https://www.eea.europa.eu/en/datahub/datahubitem-view/fa8b1229-3db6-495d-b18e-9c9b3267c02b"
LICENCE = "EEA open data"

KW_TO_HP = 1.35962

# The dataset's fuel labels, mapped onto ours. Plug-in hybrids appear as
# "petrol/electric"; we record them as hybrid.
FUEL_MAP = {
    "petrol": FuelType.petrol,
    "diesel": FuelType.diesel,
    "electric": FuelType.electric,
    "petrol/electric": FuelType.hybrid,
    "diesel/electric": FuelType.hybrid,
    "petrol phev": FuelType.hybrid,
}


@dataclass
class EeaImportResult:
    country: str
    fetched: int
    inserted: int
    updated: int
    makes: int
    models: int


def build_query(country: str, min_registrations: int) -> str:
    """Group raw registrations into distinct specs.

    One row per (make, name, fuel, capacity, power, consumption, mass) rather
    than per registration, which turns ~125k Irish rows into ~1k specs.
    """
    return f"""
        SELECT [Mk], [Cn], [Ft], [Ec (cm3)] AS cc, [Ep (KW)] AS kw,
               [Fc] AS l100, [M (kg)] AS kg, [Z (Wh/km)] AS wh_km,
               COUNT(*) AS regs
        FROM {TABLE}
        WHERE [MS] = '{country}' AND [Mk] IS NOT NULL AND [Cn] IS NOT NULL
        GROUP BY [Mk], [Cn], [Ft], [Ec (cm3)], [Ep (KW)], [Fc], [M (kg)], [Z (Wh/km)]
        HAVING COUNT(*) >= {min_registrations}
    """.strip()


def fetch(country: str = "IE", min_registrations: int = 3, timeout: float = 180.0) -> list[dict]:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        r = client.get(SQL_ENDPOINT, params={"query": build_query(country, min_registrations)})
        r.raise_for_status()
        payload = r.json()

    if "results" not in payload:
        raise ValueError(f"unexpected response from EEA: {str(payload)[:200]}")
    return payload["results"]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _title(make: str) -> str:
    """Source shouts makes in caps; render them the way a person writes them."""
    cleaned = _clean(make).title()
    # Keep well-known all-caps marques intact.
    for marque in ("BMW", "MG", "DS", "BYD", "KGM", "SEAT", "CUPRA"):
        if cleaned.upper() == marque:
            return marque
    return cleaned


def make_row_id(row: dict) -> str:
    """Stable id so re-importing updates in place."""
    parts = [
        "eea",
        _clean(row["Mk"]).lower().replace(" ", "-"),
        _clean(row["Cn"]).lower().replace(" ", "-"),
        str(row.get("Ft") or "").replace("/", "-"),
        str(row.get("cc") or "x"),
        str(row.get("kw") or "x"),
        str(row.get("l100") or "x"),
    ]
    slug = "-".join(parts)
    return re.sub(r"[^a-z0-9\-.]", "", slug.lower())[:160]


def describe_variant(row: dict) -> str:
    """A human label, since the dataset has no trim names."""
    bits = []
    if row.get("cc"):
        bits.append(f"{int(row['cc'])}cc")
    if row.get("kw"):
        bits.append(f"{round(float(row['kw']) * KW_TO_HP)}hp")
    fuel = _clean(row.get("Ft")).replace("/", "/")
    if fuel:
        bits.append(fuel)
    if row.get("l100"):
        bits.append(f"{float(row['l100']):.1f} L/100km")
    label = " · ".join(bits)
    return f"{_clean(row['Cn'])} ({label})" if label else _clean(row["Cn"])


def to_catalog_values(row: dict, country: str) -> dict | None:
    fuel = FUEL_MAP.get(_clean(row.get("Ft")).lower())
    if fuel is None:
        return None  # unknown fuel label — skip rather than guess

    kw = row.get("kw")
    is_electric = fuel == FuelType.electric

    return {
        "make": _title(row["Mk"]),
        "model": _clean(row["Cn"]),
        "variant": describe_variant(row),
        "model_year": None,
        "fuel_type": fuel,
        # EVs are single-speed; for combustion the dataset says nothing, so
        # leave it blank rather than assert a gearbox it never recorded.
        "transmission": Transmission.single_speed.value if is_electric else None,
        "engine_size_cc": int(row["cc"]) if row.get("cc") else None,
        "fuel_consumption_l_per_100km": float(row["l100"]) if row.get("l100") else None,
        "horsepower": round(float(kw) * KW_TO_HP) if kw else None,
        "kerb_weight_kg": int(row["kg"]) if row.get("kg") else None,
        # Wh/km -> kWh/100km
        "consumption_real_world_kwh_100km": (
            round(float(row["wh_km"]) / 10.0, 2) if row.get("wh_km") else None
        ),
        "country": country,
        "registration_count": int(row.get("regs") or 0),
        "data_quality": "registration data",
    }


def ingest(
    db: Session,
    country: str = "IE",
    min_registrations: int = 3,
    rows: list[dict] | None = None,
) -> EeaImportResult:
    if rows is None:
        rows = fetch(country=country, min_registrations=min_registrations)

    existing = {
        c.id: c
        for c in db.scalars(
            select(CatalogVehicle).where(CatalogVehicle.source == CatalogSource.eea)
        )
    }

    inserted = updated = 0
    seen: set[str] = set()

    for row in rows:
        values = to_catalog_values(row, country)
        if values is None:
            continue

        row_id = make_row_id(row)
        if row_id in seen:
            continue
        seen.add(row_id)

        current = existing.get(row_id)
        if current is None:
            db.add(
                CatalogVehicle(
                    id=row_id,
                    source=CatalogSource.eea,
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

    return EeaImportResult(
        country=country,
        fetched=len(rows),
        inserted=inserted,
        updated=updated,
        makes=len({_title(r["Mk"]) for r in rows}),
        models=len({(_title(r["Mk"]), _clean(r["Cn"])) for r in rows}),
    )
