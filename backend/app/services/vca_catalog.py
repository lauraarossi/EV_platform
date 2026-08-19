"""Ingest the UK Vehicle Certification Agency's new-car fuel consumption data.

This is the only source we have that carries **trim names and transmissions**.
The EEA registration data has neither, and evdb only hides a partial trim
inside its variant names — which is why a Renault 4 "Iconic" could not be found
at all before this.

It is Crown copyright, free to use, and covers cars on sale in the UK: the same
right-hand-drive models sold in Ireland.

**It cannot be fetched automatically.** The download sits behind an ASP.NET
postback form that redirects to the site root when requested directly, so the
zip is committed to the repo under `data/vca/` and refreshed by hand. That is
also why the file is small enough to commit — it is a zip, not the 1.4 MB CSV.

Format notes, from the 17-08-2026 file (5,452 rows):
  * Encoded cp1252, not UTF-8.
  * `Description` is the trim, lower-cased and often carrying the power too:
    "iconic 150 hp comfort range".
  * `Transmission` is a code — A8, M6, A1 — where the letter is the type and
    the digit the gear count. `Manual or Automatic` spells it out.
  * `WLTP Metric Combined` is L/100km; blank for pure EVs.
  * Fuel labels are their own: "Electricity", "Petrol Electric", and so on.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.catalog import CatalogVehicle, CatalogSource
from app.models.vehicle import FuelType, Transmission

SOURCE_NAME = "VCA New Car Fuel Consumption (UK)"
SOURCE_URL = "https://carfueldata.vehicle-certification-agency.gov.uk/"
LICENCE = "Crown copyright"

# Where the manually downloaded zips live. The repo keeps them beside the
# backend, while the container copies them inside it, so both layouts are
# tried rather than assuming one. VCA_DATA_DIR overrides either.
_HERE = Path(__file__).resolve()
DATA_DIR_CANDIDATES = (
    _HERE.parents[2].parent / "data" / "vca",   # repo:      <root>/data/vca
    _HERE.parents[2] / "data" / "vca",          # container: /app/data/vca
)

ENCODING = "cp1252"

FUEL_MAP = {
    "petrol": FuelType.petrol,
    "diesel": FuelType.diesel,
    "electricity": FuelType.electric,
    # Anything pairing a fuel with electricity is a hybrid of some flavour.
    "petrol electric": FuelType.hybrid,
    "diesel electric": FuelType.hybrid,
    "electricity / petrol": FuelType.hybrid,
    "electricity / diesel": FuelType.hybrid,
    "petrol / lpg": FuelType.petrol,
}


@dataclass
class VcaImportResult:
    file: str
    fetched: int
    inserted: int
    updated: int
    makes: int
    models: int
    with_trim: int


def data_dir() -> Path:
    """The first data directory that actually exists, so the same code works
    from a checkout and from the container image."""
    override = (settings.vca_data_dir or "").strip()
    candidates = (Path(override),) if override else DATA_DIR_CANDIDATES
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    tried = ", ".join(str(c) for c in candidates)
    raise FileNotFoundError(f"no VCA data directory found (tried: {tried})")


def latest_file() -> Path:
    """The newest zip in data/vca, so a refresh is just dropping a file in."""
    directory = data_dir()
    zips = sorted(directory.glob("*.zip"))
    if not zips:
        raise FileNotFoundError(f"no VCA zip found in {directory}")
    return zips[-1]


def read_rows(data: bytes) -> list[dict]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise ValueError("no CSV inside the VCA zip")
        text = z.read(names[0]).decode(ENCODING)
    return list(csv.DictReader(io.StringIO(text)))


def _clean(v: str | None) -> str:
    return re.sub(r"\s+", " ", (v or "")).strip()


def _num(v: str | None) -> float | None:
    text = _clean(v).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _title(text: str) -> str:
    """Makes arrive shouting; trims arrive whispering."""
    cleaned = _clean(text)
    if cleaned.isupper() or cleaned.islower():
        cleaned = cleaned.title()
    for marque in ("BMW", "MG", "DS", "BYD", "SEAT", "CUPRA", "KGM", "GWM"):
        if cleaned.upper() == marque:
            return marque
    return cleaned


def parse_transmission(code: str | None, manual_or_auto: str | None) -> str | None:
    """Turn "A8"/"M6" into something a person would recognise.

    The letter is the type and the digit the gear count, so A8 is an 8-speed
    automatic. "N/A" appears for EVs, which have no gearbox to describe.
    """
    code = _clean(code).upper()
    spelled = _clean(manual_or_auto).lower()

    if spelled.startswith("electric"):
        return Transmission.single_speed.value
    if not code or code in {"N/A", "NA", "-"}:
        return Transmission.single_speed.value if spelled.startswith("electric") else None

    m = re.match(r"^([A-Z]+)(\d+)?$", code)
    if not m:
        return code  # keep whatever it says rather than dropping it
    letters, gears = m.group(1), m.group(2)

    kind = {
        "M": "Manual",
        "A": "Automatic",
        "AV": "CVT",
        "CVT": "CVT",
        "D": "Dual-clutch",
        "DCT": "Dual-clutch",
        "SA": "Semi-automatic",
    }.get(letters)

    if kind is None:
        return f"{code}" if not spelled else _title(spelled)
    return f"{gears}-speed {kind}" if gears else kind


# Engine and marketing codes that shouldn't be title-cased into nonsense.
_KEEP_CASE = {
    "tce": "TCe", "tsi": "TSI", "tdi": "TDI", "tfsi": "TFSI", "dci": "dCi",
    "hdi": "HDi", "bluehdi": "BlueHDi", "gti": "GTI", "gt": "GT", "rs": "RS",
    "ev": "EV", "phev": "PHEV", "hev": "HEV", "awd": "AWD", "4wd": "4WD",
    "suv": "SUV", "cvt": "CVT", "amg": "AMG", "bmw": "BMW", "mhev": "MHEV",
}


def clean_trim(description: str, model: str) -> str | None:
    """The Description column is the trim, but its casing is all over the place.

    The source mixes "iconic 150hp comfort range" with "Iconic 150 Hp Comfort
    Range", so it is normalised: title case, a consistent "150hp", and engine
    codes left in the case people actually write them.
    """
    text = _clean(description)
    if not text:
        return None
    if model and text.lower().startswith(model.lower()):
        text = text[len(model):].strip(" -–")
    if not text:
        return None

    # "150 Hp" and "150hp" are the same thing; settle on one.
    text = re.sub(r"(\d+)\s*hp\b", r"\1hp", text, flags=re.I)

    words = []
    for word in text.split():
        bare = word.lower().strip("()[],.")
        if bare in _KEEP_CASE:
            words.append(word.lower().replace(bare, _KEEP_CASE[bare]))
        elif re.match(r"^\d+hp$", word, flags=re.I):
            words.append(word.lower())
        elif word.isupper() and len(word) > 1:
            words.append(word)          # already an acronym, leave it
        else:
            words.append(word[:1].upper() + word[1:].lower())
    return " ".join(words) or None


def stated_power(description: str) -> int | None:
    """The power a trim name explicitly claims, e.g. "iconic 150 hp".

    Only an explicit "hp" counts. A bare number in a name is often not power
    at all — a BMW 320i is not 320 hp — so those are ignored.
    """
    m = re.search(r"(\d{2,4})\s*hp\b", description or "", flags=re.I)
    return int(m.group(1)) if m else None



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
    """Keyed on the trim as kept, not on the raw Description.

    The source writes the same car both ways — "Mazda CX-60 2.5 327ps Exclusive"
    in one row and "2.5 327ps Exclusive" in another. `clean_trim` strips the
    model prefix from both, so they displayed identically while hashing to two
    different ids, and the picker listed the car twice.
    """
    model = _clean(row.get("Model"))
    parts = [
        "vca",
        _clean(row.get("Manufacturer")),
        model,
        clean_trim(row.get("Description", ""), model) or "",
        _clean(row.get("Engine Capacity")),
        _clean(row.get("Engine Power (PS)")),
        _clean(row.get("Transmission")),
    ]
    slug = re.sub(r"[^a-z0-9]+", "-", "-".join(parts).lower()).strip("-")
    return slug[:160]


def to_catalog_values(row: dict) -> dict | None:
    fuel = FUEL_MAP.get(_clean(row.get("Fuel Type")).lower())
    if fuel is None:
        return None

    make = _title(row.get("Manufacturer", ""))
    model = _clean(row.get("Model"))
    if not make or not model:
        return None

    trim = clean_trim(row.get("Description", ""), model)
    ps = _num(row.get("Engine Power (PS)"))

    # The trim name and the PS column disagree on 68 rows, and for two
    # different reasons. 67 are hybrids, where the name quotes *system* power
    # (engine plus motor) and the column quotes engine power alone — both
    # correct, measuring different things. The remaining one is a pure EV, a
    # Renault 4 "evolution 120 hp" declaring 150 PS while carrying the 40 kWh
    # car's 301 km range, which is simply an error.
    #
    # Either way the trim-name figure is the one to keep: it is what the car is
    # sold as, and for a comparison tool total output is the meaningful number.
    # The disagreement is recorded rather than hidden.
    claimed = stated_power(row.get("Description", ""))
    power_disputed = bool(
        claimed and ps and abs(claimed - ps) / max(claimed, ps) > 0.05
    )
    if power_disputed:
        ps = float(claimed)
    cc = _num(row.get("Engine Capacity"))
    l100 = _num(row.get("WLTP Metric Combined"))
    wh_km = _num(row.get("wh/km"))
    range_km = _num(row.get("Maximum range (Km)"))

    label = " · ".join(
        bit
        for bit in (
            trim,
            f"{int(cc)}cc" if cc else None,
            f"{int(ps)}hp" if ps else None,
            f"{l100:.1f} L/100km" if l100 else None,
        )
        if bit
    )

    return {
        "make": make,
        "model": model,
        "variant": f"{model} ({label})" if label else model,
        "trim": trim,
        "model_year": None,
        "fuel_type": fuel,
        "transmission": parse_transmission(
            row.get("Transmission"), row.get("Manual or Automatic")
        ),
        "engine_size_cc": int(cc) if cc else None,
        "fuel_consumption_l_per_100km": l100,
        # PS and hp differ by under 1.5%; the column is already the metric one.
        "horsepower": int(ps) if ps else None,
        "wltp_range_km": range_km,
        "consumption_real_world_kwh_100km": round(wh_km / 10.0, 2) if wh_km else None,
        "country": "GB",
        "registration_count": None,
        "data_quality": (
            "manufacturer declared; power taken from the trim name, which "
            "differs from the declared engine PS"
            if power_disputed
            else "manufacturer declared"
        ),
    }


def ingest(
    db: Session,
    data: bytes | None = None,
    path: Path | None = None,
    name: str | None = None,
) -> VcaImportResult:
    source = path or (None if data else latest_file())
    if data is None:
        data = source.read_bytes()

    rows = read_rows(data)

    existing = {
        c.id: c
        for c in db.scalars(
            select(CatalogVehicle).where(CatalogVehicle.source == CatalogSource.vca)
        )
    }

    inserted = updated = 0
    seen: dict[str, dict] = {}

    for row in rows:
        values = to_catalog_values(row)
        if values is None:
            continue
        seen.setdefault(make_row_id(row), values)

    for row_id, values in seen.items():
        current = existing.get(row_id)
        if current is None:
            db.add(
                CatalogVehicle(
                    id=row_id,
                    source=CatalogSource.vca,
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
    # Anything this file no longer describes, including rows left behind by an
    # earlier id scheme.
    prune_missing(db, CatalogSource.vca, set(seen))

    return VcaImportResult(
        file=source.name if source else (name or "uploaded"),
        fetched=len(rows),
        inserted=inserted,
        updated=updated,
        makes=len({v["make"] for v in seen.values()}),
        models=len({(v["make"], v["model"]) for v in seen.values()}),
        with_trim=sum(1 for v in seen.values() if v["trim"]),
    )
