"""EEA registration-data import and the merge with evdb."""
import pytest

from app.models import CatalogVehicle, CatalogSource, FuelType, Transmission
from app.services import eea_catalog, merge_catalog


def eea_row(mk="RENAULT", cn="CAPTUR", ft="petrol", cc=999, kw=67, l100=5.9, kg=1300, wh=None, regs=344):
    return {
        "Mk": mk, "Cn": cn, "Ft": ft, "cc": cc, "kw": kw,
        "l100": l100, "kg": kg, "wh_km": wh, "regs": regs,
    }


def test_maps_combustion_specs(db):
    """The gap evdb couldn't fill: engine size and fuel consumption."""
    eea_catalog.ingest(db, rows=[eea_row()])
    row = db.query(CatalogVehicle).one()

    assert row.make == "Renault"
    assert row.model == "CAPTUR"
    assert row.fuel_type == FuelType.petrol
    assert row.engine_size_cc == 999
    assert row.horsepower == 91          # 67 kW x 1.35962
    assert row.fuel_consumption_l_per_100km == 5.9
    assert row.kerb_weight_kg == 1300
    assert row.registration_count == 344
    assert row.country == "IE"


def test_variant_label_describes_the_engine(db):
    """There are no trim names in this source, so the label has to carry the
    engine detail or the options are indistinguishable."""
    eea_catalog.ingest(db, rows=[eea_row()])
    assert db.query(CatalogVehicle).one().variant == "CAPTUR (999cc · 91hp · petrol · 5.9 L/100km)"


def test_electric_rows_convert_wh_per_km(db):
    eea_catalog.ingest(db, rows=[eea_row(cn="RENAULT 4 E-TECH ELECTRIC", ft="electric",
                                         cc=None, kw=110, l100=None, wh=156)])
    row = db.query(CatalogVehicle).one()
    assert row.fuel_type == FuelType.electric
    assert row.consumption_real_world_kwh_100km == 15.6   # 156 Wh/km
    assert row.transmission == Transmission.single_speed.value
    assert row.engine_size_cc is None


def test_combustion_transmission_left_blank(db):
    """The dataset never records a gearbox, so asserting one would be invention."""
    eea_catalog.ingest(db, rows=[eea_row()])
    assert db.query(CatalogVehicle).one().transmission is None


def test_plug_in_hybrids_map_to_hybrid(db):
    eea_catalog.ingest(db, rows=[eea_row(ft="petrol/electric")])
    assert db.query(CatalogVehicle).one().fuel_type == FuelType.hybrid


def test_unknown_fuel_label_is_skipped(db):
    eea_catalog.ingest(db, rows=[eea_row(ft="hydrogen-fusion")])
    assert db.query(CatalogVehicle).count() == 0


def test_import_is_idempotent(db):
    rows = [eea_row(), eea_row(l100=6.0, regs=156)]
    first = eea_catalog.ingest(db, rows=rows)
    assert first.inserted == 2

    second = eea_catalog.ingest(db, rows=rows)
    assert second.inserted == 0 and second.updated == 0
    assert db.query(CatalogVehicle).count() == 2


def test_registration_count_updates_on_refresh(db):
    eea_catalog.ingest(db, rows=[eea_row(regs=344)])
    result = eea_catalog.ingest(db, rows=[eea_row(regs=400)])
    assert result.updated == 1
    assert db.query(CatalogVehicle).one().registration_count == 400


def test_all_caps_makes_are_tidied(db):
    eea_catalog.ingest(db, rows=[eea_row(mk="VOLKSWAGEN"), eea_row(mk="BMW", cn="I4")])
    makes = {r.make for r in db.query(CatalogVehicle)}
    assert "Volkswagen" in makes
    assert "BMW" in makes           # kept upper-case, not "Bmw"


# --- name matching between the two sources ------------------------------------

@pytest.mark.parametrize(
    "eea_make,eea_model,evdb_make,evdb_model",
    [
        ("RENAULT", "RENAULT 4 E-TECH ELECTRIC", "Renault", "4 E-Tech"),
        ("CITROEN", "E-C3", "Citroën", "ë-C3"),          # accent folding
        ("SKODA", "ENYAQ", "Škoda", "Enyaq"),            # accent folding
        ("VOLKSWAGEN, VW", "ID.3 PRO", "Volkswagen", "ID.3"),  # alias in the make field
        ("AUDI", "Q4 40 E-TRON", "Audi", "Q4 e-tron"),   # trim number + marketing suffix
    ],
)
def test_source_names_reconcile(eea_make, eea_model, evdb_make, evdb_model):
    """The two catalogues spell things differently; matching has to see through it."""
    assert merge_catalog.make_key(eea_make) == merge_catalog.make_key(evdb_make)
    a = merge_catalog.model_key(eea_make, eea_model)
    b = merge_catalog.model_key(evdb_make, evdb_model)
    assert a.startswith(b) or b.startswith(a), f"{a!r} vs {b!r}"


def _add_evdb(db, id, make, model, hp, battery, wltp):
    db.add(CatalogVehicle(
        id=id, source=CatalogSource.evdb, source_name="evdb", licence="CC BY-SA 4.0",
        make=make, model=model, variant=f"{make} {model}", fuel_type=FuelType.electric,
        horsepower=hp, battery_capacity_kwh=battery, wltp_range_km=wltp,
    ))
    db.commit()


def test_merge_fills_battery_and_range(db):
    _add_evdb(db, "evdb-r4-52", "Renault", "4 E-Tech", 150, 52.0, 400.0)
    eea_catalog.ingest(db, rows=[eea_row(cn="RENAULT 4 E-TECH ELECTRIC", ft="electric",
                                         cc=None, kw=110, l100=None, wh=156, kg=1537)])

    result = merge_catalog.enrich_from_evdb(db)
    assert result.matched == 1 and result.enriched == 1

    merged = db.query(CatalogVehicle).filter_by(source=CatalogSource.eea).one()
    assert merged.battery_capacity_kwh == 52.0     # from evdb
    assert merged.wltp_range_km == 400.0           # from evdb
    assert merged.kerb_weight_kg == 1537           # from EEA, untouched
    assert merged.enriched_from == "evdb-r4-52"


def test_merge_never_overwrites_existing_values(db):
    _add_evdb(db, "evdb-x", "Renault", "4 E-Tech", 150, 52.0, 400.0)
    eea_catalog.ingest(db, rows=[eea_row(cn="RENAULT 4 E-TECH ELECTRIC", ft="electric",
                                         cc=None, kw=110, l100=None, wh=156)])
    target = db.query(CatalogVehicle).filter_by(source=CatalogSource.eea).one()
    target.wltp_range_km = 380.0     # a figure already known
    db.commit()

    merge_catalog.enrich_from_evdb(db)
    assert target.wltp_range_km == 380.0
    assert target.battery_capacity_kwh == 52.0     # the empty one still filled


def test_merge_picks_the_variant_with_the_closest_power(db):
    """A 40 kWh and a 52 kWh car differ mainly by motor power."""
    _add_evdb(db, "evdb-40", "Renault", "4 E-Tech", 122, 42.0, 300.0)
    _add_evdb(db, "evdb-52", "Renault", "4 E-Tech", 150, 52.0, 400.0)
    eea_catalog.ingest(db, rows=[eea_row(cn="RENAULT 4 E-TECH ELECTRIC", ft="electric",
                                         cc=None, kw=110, l100=None, wh=156)])  # 110kW -> 150hp

    merge_catalog.enrich_from_evdb(db)
    merged = db.query(CatalogVehicle).filter_by(source=CatalogSource.eea).one()
    assert merged.battery_capacity_kwh == 52.0
    assert merged.enriched_from == "evdb-52"


def test_merge_leaves_petrol_rows_alone(db):
    _add_evdb(db, "evdb-r4", "Renault", "4 E-Tech", 150, 52.0, 400.0)
    eea_catalog.ingest(db, rows=[eea_row()])   # petrol Captur

    result = merge_catalog.enrich_from_evdb(db)
    assert result.considered == 0
    assert db.query(CatalogVehicle).filter_by(source=CatalogSource.eea).one().battery_capacity_kwh is None


def test_dry_run_reports_without_writing(db):
    _add_evdb(db, "evdb-r4", "Renault", "4 E-Tech", 150, 52.0, 400.0)
    eea_catalog.ingest(db, rows=[eea_row(cn="RENAULT 4 E-TECH ELECTRIC", ft="electric",
                                         cc=None, kw=110, l100=None, wh=156)])

    result = merge_catalog.enrich_from_evdb(db, dry_run=True)
    assert result.enriched == 1
    assert db.query(CatalogVehicle).filter_by(source=CatalogSource.eea).one().battery_capacity_kwh is None


def test_unmatched_models_are_reported(db):
    eea_catalog.ingest(db, rows=[eea_row(mk="SSANGYONG", cn="TORRES EVX", ft="electric",
                                         cc=None, kw=110, l100=None, wh=180)])
    result = merge_catalog.enrich_from_evdb(db)
    assert result.matched == 0
    assert result.unmatched == ["Ssangyong TORRES EVX"]
