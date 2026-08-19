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

# One table per registration year, discovered by probing the endpoint: the
# names follow co2cars_{year}{F|P}v{n}, where F is the final dataset and P the
# provisional one, and n increments by two per year. Only 2020 onwards is
# exposed over SQL — earlier years exist solely as bulk downloads.
#
# Newest first, because ingest walks them in order and keeps the most recent
# year a given spec appeared in.
TABLES: dict[int, str] = {
    2025: "co2cars_2025Pv31",   # provisional; the final is not published yet
    2024: "co2cars_2024Fv30",
    2023: "co2cars_2023Fv28",
    2022: "co2cars_2022Fv26",
    2021: "co2cars_2021Fv24",
    2020: "co2cars_2020Fv22",
}
LATEST_YEAR = max(TABLES)
SOURCE_NAME = "EEA CO2 monitoring (Regulation EU 2019/631)"
SOURCE_URL = "https://www.eea.europa.eu/en/datahub/datahubitem-view/fa8b1229-3db6-495d-b18e-9c9b3267c02b"
LICENCE = "EEA open data"

KW_TO_HP = 1.35962

# The 2020 table predates the Fc (fuel consumption) column, but every year
# reports WLTP CO2. Burning a litre of fuel releases a fixed amount of CO2, so
# consumption can be recovered from it. These are the standard EU type-approval
# factors, in grams of CO2 per litre.
CO2_PER_LITRE = {FuelType.petrol: 2392.0, FuelType.diesel: 2640.0}
YEARS_WITHOUT_FC = {2020}

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
    years: list[int]
    fetched: int
    inserted: int
    updated: int
    makes: int
    models: int


def build_query(table: str, country: str, min_registrations: int, year: int) -> str:
    """Group raw registrations into distinct specs.

    One row per (make, name, fuel, capacity, power, consumption, mass) rather
    than per registration, which turns ~125k Irish rows into ~1k specs.
    """
    # Older tables have no Fc column at all; selecting it would error rather
    # than return nulls, so it is omitted and derived from CO2 instead.
    has_fc = year not in YEARS_WITHOUT_FC
    fc_select = "[Fc] AS l100," if has_fc else "NULL AS l100,"
    fc_group = ", [Fc]" if has_fc else ""

    return f"""
        SELECT [Mk], [Cn], [Ft], [Ec (cm3)] AS cc, [Ep (KW)] AS kw,
               {fc_select} [M (kg)] AS kg, [Z (Wh/km)] AS wh_km,
               [Ewltp (g/km)] AS co2,
               COUNT(*) AS regs
        FROM [CO2Emission].[latest].[{table}]
        WHERE [MS] = '{country}' AND [Mk] IS NOT NULL AND [Cn] IS NOT NULL
        GROUP BY [Mk], [Cn], [Ft], [Ec (cm3)], [Ep (KW)]{fc_group}, [M (kg)],
                 [Z (Wh/km)], [Ewltp (g/km)]
        HAVING COUNT(*) >= {min_registrations}
    """.strip()


def fetch_year(
    year: int, country: str = "IE", min_registrations: int = 3, timeout: float = 240.0
) -> list[dict]:
    table = TABLES.get(year)
    if table is None:
        raise ValueError(f"no table for {year}; available: {sorted(TABLES)}")

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        r = client.get(
            SQL_ENDPOINT, params={"query": build_query(table, country, min_registrations, year)}
        )
        r.raise_for_status()
        payload = r.json()

    if "results" not in payload:
        raise ValueError(f"unexpected response from EEA for {year}: {str(payload)[:200]}")
    return payload["results"]


def fetch(country: str = "IE", min_registrations: int = 3, timeout: float = 240.0) -> list[dict]:
    """Just the newest year — kept for callers that only want current cars."""
    return fetch_year(LATEST_YEAR, country, min_registrations, timeout)


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



def prune_missing(db: Session, source, seen_ids: set) -> int:
    """Drop rows of this source that the latest import no longer produced.

    Without this an import only ever adds. Change how ids are built, or let the
    source retire a variant, and the old rows sit in the catalogue for good —
    which is how the picker came to list the same car twice.

    Guarded so a truncated download cannot take the catalogue with it: if the
    import produced less than half of what is already stored, something went
    wrong upstream and nothing is deleted.
    """
    existing = {
        c.id
        for c in db.scalars(select(CatalogVehicle).where(CatalogVehicle.source == source))
    }
    stale = existing - seen_ids
    if not stale or len(seen_ids) * 2 < len(existing):
        return 0
    db.query(CatalogVehicle).filter(CatalogVehicle.id.in_(stale)).delete(
        synchronize_session=False
    )
    db.commit()
    return len(stale)


def make_row_id(row: dict) -> str:
    """Stable id so re-importing updates in place.

    Consumption is deliberately not part of it. It is derived from CO2 when the
    source omits it, so a row missing the raw figure keyed as "x" while showing
    the same derived value as its twin — two ids, one visible car.
    """
    parts = [
        "eea",
        _clean(row["Mk"]).lower().replace(" ", "-"),
        _clean(row["Cn"]).lower().replace(" ", "-"),
        str(row.get("Ft") or "").replace("/", "-"),
        str(row.get("cc") or "x"),
        str(row.get("kw") or "x"),
    ]
    slug = "-".join(parts)
    return re.sub(r"[^a-z0-9\-.]", "", slug.lower())[:160]


def describe_variant(row: dict, litres: float | None = None) -> str:
    """A human label, since the dataset has no trim names."""
    bits = []
    if row.get("cc"):
        bits.append(f"{int(row['cc'])}cc")
    if row.get("kw"):
        bits.append(f"{round(float(row['kw']) * KW_TO_HP)}hp")
    fuel = _clean(row.get("Ft")).replace("/", "/")
    if fuel:
        bits.append(fuel)
    consumption = litres if litres is not None else (
        float(row["l100"]) if row.get("l100") else None
    )
    if consumption:
        bits.append(f"{consumption:.1f} L/100km")
    label = " · ".join(bits)
    return f"{_clean(row['Cn'])} ({label})" if label else _clean(row["Cn"])


def to_catalog_values(row: dict, country: str, year: int | None = None) -> dict | None:
    fuel = FUEL_MAP.get(_clean(row.get("Ft")).lower())
    if fuel is None:
        return None  # unknown fuel label — skip rather than guess

    kw = row.get("kw")
    is_electric = fuel == FuelType.electric

    litres = float(row["l100"]) if row.get("l100") else None
    derived = False
    if litres is None and row.get("co2") and fuel in CO2_PER_LITRE:
        # g/km -> litres/100km via the fixed CO2 content of a litre of fuel.
        litres = round(float(row["co2"]) * 100.0 / CO2_PER_LITRE[fuel], 2)
        derived = True

    return {
        "make": _title(row["Mk"]),
        "model": _clean(row["Cn"]),
        "variant": describe_variant(row, litres),
        # This dataset has no trim names — Cn is the commercial name. Leaving
        # it null is honest; stuffing the engine label in here was not.
        "trim": None,
        "model_year": year,
        "fuel_type": fuel,
        # EVs are single-speed; for combustion the dataset says nothing, so
        # leave it blank rather than assert a gearbox it never recorded.
        "transmission": Transmission.single_speed.value if is_electric else None,
        "engine_size_cc": int(row["cc"]) if row.get("cc") else None,
        "fuel_consumption_l_per_100km": litres,
        "horsepower": round(float(kw) * KW_TO_HP) if kw else None,
        "kerb_weight_kg": int(row["kg"]) if row.get("kg") else None,
        # Wh/km -> kWh/100km
        "consumption_real_world_kwh_100km": (
            round(float(row["wh_km"]) / 10.0, 2) if row.get("wh_km") else None
        ),
        "country": country,
        "registration_count": int(row.get("regs") or 0),
        "data_quality": "registration data (consumption from CO2)" if derived
        else "registration data",
    }


def ingest(
    db: Session,
    country: str = "IE",
    min_registrations: int = 3,
    years: list[int] | None = None,
    rows: list[dict] | None = None,
) -> EeaImportResult:
    """Import one or more registration years.

    The same car sold across several years would otherwise appear as a
    near-duplicate per year, cluttering the picker. So every year is folded
    into one entry per spec first, then written once: registrations are summed
    across years, and `model_year` keeps the most recent year the spec was
    still being sold — which is what marks a car as discontinued.
    """
    # Bound here because only the fetching path sets it, and pruning needs to
    # know whether this import covered the whole catalogue or one year of it.
    wanted: list[int] = []

    if rows is not None:
        # Direct rows are used by the tests; treat them as a single year.
        batches = [(years[0] if years else LATEST_YEAR, rows)]
    else:
        wanted = sorted(years or [LATEST_YEAR], reverse=True)
        unknown = [y for y in wanted if y not in TABLES]
        if unknown:
            raise ValueError(f"no data for {unknown}; available: {sorted(TABLES)}")
        batches = [
            (year, fetch_year(year, country=country, min_registrations=min_registrations))
            for year in wanted
        ]

    # --- fold every year into one entry per spec ---------------------------
    aggregated: dict[str, dict] = {}
    fetched = 0

    for year, batch in batches:
        fetched += len(batch)
        for row in batch:
            values = to_catalog_values(row, country, year)
            if values is None:
                continue

            row_id = make_row_id(row)
            seen = aggregated.get(row_id)
            if seen is None:
                aggregated[row_id] = values
                continue

            seen["registration_count"] = (seen.get("registration_count") or 0) + (
                values.get("registration_count") or 0
            )
            # Newest wins, whatever order the batches arrived in.
            if (values.get("model_year") or 0) > (seen.get("model_year") or 0):
                seen["model_year"] = values["model_year"]

    # --- write ------------------------------------------------------------
    existing = {
        c.id: c
        for c in db.scalars(
            select(CatalogVehicle).where(CatalogVehicle.source == CatalogSource.eea)
        )
    }

    inserted = updated = 0
    for row_id, values in aggregated.items():
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
    # Only when this import covered every year available. Importing a single
    # year produces a fraction of the catalogue, and pruning against that would
    # delete every other year's cars.
    if set(wanted) == set(TABLES):
        prune_missing(db, CatalogSource.eea, set(aggregated))

    return EeaImportResult(
        country=country,
        years=[y for y, _ in batches],
        fetched=fetched,
        inserted=inserted,
        updated=updated,
        makes=len({v["make"] for v in aggregated.values()}),
        models=len({(v["make"], v["model"]) for v in aggregated.values()}),
    )
