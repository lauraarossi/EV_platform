"""Tests for the EV catalogue import and the cascading lookups.

The fixture mirrors the real evdb schema (verified against the Feb 2026
release), so these run offline but still fail if the mapping drifts.
"""
import sqlite3
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import CatalogVehicle, CatalogSource, FuelType, Transmission
from app.services import ev_catalog


def build_snapshot(variants=None) -> bytes:
    """A minimal evdb-shaped SQLite file."""
    path = Path(tempfile.mkdtemp()) / "evdb.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE vehicle_models (
            id TEXT PRIMARY KEY, manufacturer_id TEXT, brand TEXT, name TEXT,
            body_style TEXT, image_url TEXT
        );
        CREATE TABLE vehicle_variants (
            id TEXT PRIMARY KEY, model_id TEXT, variant_name TEXT, model_year INTEGER,
            trim_level TEXT, battery_capacity_kwh REAL, battery_usable_kwh REAL,
            ac_onboard_charger_kw REAL, dc_charge_power_kw REAL, range_wltp_km REAL,
            consumption_wltp_kwh_100km REAL, consumption_real_world_kwh_100km REAL,
            total_power_kw REAL, acceleration_0_100_sec REAL, top_speed_kph REAL,
            weight_curb_kg REAL, data_quality TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO vehicle_models VALUES ('renault-4-e-tech','renault-group','Renault','4 E-Tech','hatchback',NULL)"
    )
    # A model with no brand — must be skipped rather than imported as blank.
    conn.execute(
        "INSERT INTO vehicle_models VALUES ('mystery','x',NULL,'Unknown','suv',NULL)"
    )
    conn.execute(
        "INSERT INTO vehicle_variants VALUES ('mystery-1','mystery','Mystery',2025,NULL,"
        "50,48,NULL,NULL,350,NULL,NULL,100,9.0,150,1400,'draft')"
    )

    rows = variants if variants is not None else [
        (
            "renault-4-e-tech-techno-52-2025", "renault-4-e-tech",
            "Renault 4 E-Tech Electric Techno 52", 2025, None,
            52.0, 50.0, None, None, 400.0, 14.8, 16.5, 110.0, 8.0, 150.0, 1440.0, "verified",
        ),
        (
            "renault-4-e-tech-evolution-40-2025", "renault-4-e-tech",
            "Renault 4 E-Tech Electric Evolution 40", 2025, None,
            42.0, 40.0, None, None, 300.0, 15.2, 17.0, 90.0, 9.5, 150.0, 1360.0, "verified",
        ),
    ]
    conn.executemany(
        f"INSERT INTO vehicle_variants VALUES ({','.join('?' * 17)})", rows
    )
    conn.commit()
    conn.close()
    return path.read_bytes()


def test_maps_specs_onto_our_fields(db):
    ev_catalog.ingest(db, db_bytes=build_snapshot())

    techno = db.get(CatalogVehicle, "renault-4-e-tech-techno-52-2025")
    assert techno.make == "Renault"
    assert techno.model == "4 E-Tech"
    assert techno.variant == "Renault 4 E-Tech Electric Techno 52"
    assert techno.battery_capacity_kwh == 52.0
    assert techno.wltp_range_km == 400.0
    assert techno.zero_to_100_seconds == 8.0
    assert techno.top_speed_kmh == 150
    assert techno.kerb_weight_kg == 1440
    assert techno.consumption_real_world_kwh_100km == 16.5


def test_converts_kw_to_horsepower(db):
    """The source stores motor power in kW; the form asks for hp."""
    ev_catalog.ingest(db, db_bytes=build_snapshot())
    techno = db.get(CatalogVehicle, "renault-4-e-tech-techno-52-2025")
    assert techno.horsepower == 150  # 110 kW x 1.35962


def test_defaults_to_electric_and_single_speed(db):
    ev_catalog.ingest(db, db_bytes=build_snapshot())
    techno = db.get(CatalogVehicle, "renault-4-e-tech-techno-52-2025")
    assert techno.fuel_type == FuelType.electric
    assert techno.transmission == Transmission.single_speed.value


def test_records_attribution(db):
    """CC BY-SA data must carry its source and licence."""
    ev_catalog.ingest(db, db_bytes=build_snapshot())
    entry = db.get(CatalogVehicle, "renault-4-e-tech-techno-52-2025")
    assert entry.source == CatalogSource.evdb
    assert entry.licence == "CC BY-SA 4.0"
    assert entry.source_url == "https://github.com/gaia-charge/evdb"


def test_skips_models_without_a_brand(db):
    ev_catalog.ingest(db, db_bytes=build_snapshot())
    assert db.get(CatalogVehicle, "mystery-1") is None


def test_import_is_idempotent(db):
    snap = build_snapshot()
    first = ev_catalog.ingest(db, db_bytes=snap)
    assert first.inserted == 2 and first.updated == 0

    second = ev_catalog.ingest(db, db_bytes=snap)
    assert second.inserted == 0 and second.updated == 0
    assert db.query(CatalogVehicle).count() == 2


def test_refresh_updates_a_revised_spec(db):
    ev_catalog.ingest(db, db_bytes=build_snapshot())

    revised = build_snapshot(variants=[(
        "renault-4-e-tech-techno-52-2025", "renault-4-e-tech",
        "Renault 4 E-Tech Electric Techno 52", 2025, None,
        52.0, 50.0, None, None, 409.0, 14.8, 16.5, 110.0, 8.0, 150.0, 1440.0, "verified",
    )])
    result = ev_catalog.ingest(db, db_bytes=revised)

    assert result.updated == 1
    assert db.get(CatalogVehicle, "renault-4-e-tech-techno-52-2025").wltp_range_km == 409.0


def test_result_counts_makes_and_models(db):
    r = ev_catalog.ingest(db, db_bytes=build_snapshot())
    assert r.fetched == 2
    assert r.makes == 1
    assert r.models == 1


def test_cascade_narrows_makes_to_models_to_variants(db):
    """The picker's three steps, exercised the way the UI walks them."""
    ev_catalog.ingest(db, db_bytes=build_snapshot())

    makes = db.scalars(select(CatalogVehicle.make).distinct()).all()
    assert makes == ["Renault"]

    models = db.scalars(
        select(CatalogVehicle.model).where(CatalogVehicle.make == "Renault").distinct()
    ).all()
    assert models == ["4 E-Tech"]

    variants = db.scalars(
        select(CatalogVehicle).where(
            CatalogVehicle.make == "Renault", CatalogVehicle.model == "4 E-Tech"
        )
    ).all()
    assert {v.variant for v in variants} == {
        "Renault 4 E-Tech Electric Techno 52",
        "Renault 4 E-Tech Electric Evolution 40",
    }


def test_charging_specs_absent_upstream_stay_null(db):
    """The source has no charging data, so these must not be invented."""
    ev_catalog.ingest(db, db_bytes=build_snapshot())
    entry = db.get(CatalogVehicle, "renault-4-e-tech-techno-52-2025")
    assert entry.onboard_charger_kw is None
    assert entry.dc_charge_power_kw is None


def test_missing_power_leaves_horsepower_null(db):
    snap = build_snapshot(variants=[(
        "x-1", "renault-4-e-tech", "No Power Variant", 2025, None,
        50.0, 48.0, None, None, 350.0, None, None, None, None, 150.0, 1400.0, "draft",
    )])
    ev_catalog.ingest(db, db_bytes=snap)
    assert db.get(CatalogVehicle, "x-1").horsepower is None


# --- trim names ---------------------------------------------------------------

@pytest.mark.parametrize(
    "variant,make,model,expected",
    [
        ("Renault 4 E-Tech Electric Techno 52", "Renault", "4 E-Tech", "Techno 52"),
        ("Renault 4 E-Tech Electric Evolution 40", "Renault", "4 E-Tech", "Evolution 40"),
        ("Audi Q4 e-tron 45", "Audi", "Q4 e-tron", "45"),
        # The variant doesn't always repeat the model name exactly.
        ("Renault Megane E-Tech EV60 Iconic", "Renault", "Megane E-Tech Electric", "EV60 Iconic"),
        ("Renault Scenic E-Tech Comfort Range", "Renault", "Scenic E-Tech Electric", "Comfort Range"),
        ("Renault Zoe ZE50 R135", "Renault", "Zoe", "ZE50 R135"),
        # Nothing beyond the model name means there is no trim to report.
        ("Renault Zoe", "Renault", "Zoe", None),
        ("Zoe", "Renault", "Zoe", None),
    ],
)
def test_trim_is_pulled_out_of_the_variant_name(variant, make, model, expected):
    assert ev_catalog.derive_trim(variant, make, model) == expected


def test_trim_is_stored_on_import(db):
    ev_catalog.ingest(db, db_bytes=build_snapshot())
    entry = db.get(CatalogVehicle, "renault-4-e-tech-techno-52-2025")
    assert entry.trim == "Techno 52"
