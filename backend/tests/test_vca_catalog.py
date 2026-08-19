"""VCA import — the only source carrying trim names and transmissions."""
import csv
import io
import zipfile

import pytest

from app.models import CatalogVehicle, CatalogSource, FuelType, Transmission
from app.services import vca_catalog

COLUMNS = [
    "Manufacturer", "Model", "Description", "Transmission", "Manual or Automatic",
    "Engine Capacity", "Fuel Type", "Powertrain", "Engine Power (PS)",
    "Engine Power (Kw)", "wh/km", "Maximum range (Km)", "WLTP Metric Combined",
    "WLTP CO2",
]


def vca_row(**over):
    row = {
        "Manufacturer": "RENAULT", "Model": "Renault 4 E-Tech electric",
        "Description": "iconic 150 hp comfort range", "Transmission": "N/A",
        "Manual or Automatic": "Electric - Not Applicable", "Engine Capacity": "",
        "Fuel Type": "Electricity", "Powertrain": "Pure Electric Vehicle (PEV)",
        "Engine Power (PS)": "150", "Engine Power (Kw)": "110", "wh/km": "156",
        "Maximum range (Km)": "396", "WLTP Metric Combined": "", "WLTP CO2": "0",
    }
    row.update(over)
    return row


def build_zip(rows=None) -> bytes:
    rows = rows if rows is not None else [vca_row()]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS)
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in COLUMNS})

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        # The real file is cp1252, not UTF-8.
        z.writestr("Euro_6_latest.csv", buf.getvalue().encode("cp1252"))
    return out.getvalue()


# --- the point of this source -------------------------------------------------

def test_trim_names_finally_arrive(db):
    """Neither other source has these; a Renault 4 "Iconic" was unfindable."""
    vca_catalog.ingest(db, data=build_zip())
    assert db.query(CatalogVehicle).one().trim == "Iconic 150hp Comfort Range"


def test_transmission_codes_become_readable(db):
    vca_catalog.ingest(db, data=build_zip([
        vca_row(Description="techno TCe 90", Transmission="M6",
                **{"Manual or Automatic": "Manual", "Fuel Type": "Petrol",
                   "Engine Capacity": "999", "WLTP Metric Combined": "5.9"}),
    ]))
    assert db.query(CatalogVehicle).one().transmission == "6-speed Manual"


@pytest.mark.parametrize(
    "code,spelled,expected",
    [
        ("M6", "Manual", "6-speed Manual"),
        ("A8", "Automatic", "8-speed Automatic"),
        ("A1", "Automatic", "1-speed Automatic"),
        ("AV", "Automatic", "CVT"),
        # EVs have no gearbox to describe.
        ("N/A", "Electric - Not Applicable", Transmission.single_speed.value),
    ],
)
def test_transmission_parsing(code, spelled, expected):
    assert vca_catalog.parse_transmission(code, spelled) == expected


def test_unparseable_transmission_is_kept_not_dropped():
    assert vca_catalog.parse_transmission("WEIRD-1", "") == "WEIRD-1"


# --- the source's casing is inconsistent -------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("iconic 150 hp comfort range", "Iconic 150hp Comfort Range"),
        ("Iconic 150Hp Comfort Range", "Iconic 150hp Comfort Range"),
        ("techno TCe 90", "Techno TCe 90"),
        ("R.S. Line Tce 140 Mild Hybrid", "R.S. Line TCe 140 Mild Hybrid"),
        ("", None),
    ],
)
def test_trim_casing_is_normalised(raw, expected):
    """The same trim appears as both "150 Hp" and "150hp" in one file."""
    assert vca_catalog.clean_trim(raw, "") == expected


def test_model_prefix_is_stripped_from_the_trim():
    assert vca_catalog.clean_trim("Captur techno", "Captur") == "Techno"


# --- field mapping ------------------------------------------------------------

def test_petrol_specs_map_across(db):
    vca_catalog.ingest(db, data=build_zip([
        vca_row(Description="techno TCe 90", Transmission="M6",
                **{"Manual or Automatic": "Manual", "Fuel Type": "Petrol",
                   "Model": "CAPTUR", "Engine Capacity": "999",
                   "Engine Power (PS)": "91", "WLTP Metric Combined": "5.9"}),
    ]))
    row = db.query(CatalogVehicle).one()
    assert row.fuel_type == FuelType.petrol
    assert row.engine_size_cc == 999
    assert row.horsepower == 91
    assert row.fuel_consumption_l_per_100km == 5.9


def test_electric_rows_carry_range_and_consumption(db):
    vca_catalog.ingest(db, data=build_zip())
    row = db.query(CatalogVehicle).one()
    assert row.fuel_type == FuelType.electric
    assert row.wltp_range_km == 396.0
    assert row.consumption_real_world_kwh_100km == 15.6      # 156 Wh/km
    assert row.fuel_consumption_l_per_100km is None


@pytest.mark.parametrize(
    "label,expected",
    [
        ("Petrol", FuelType.petrol),
        ("Diesel", FuelType.diesel),
        ("Electricity", FuelType.electric),
        ("Petrol Electric", FuelType.hybrid),
        ("Electricity / Petrol", FuelType.hybrid),
    ],
)
def test_fuel_labels_map(db, label, expected):
    vca_catalog.ingest(db, data=build_zip([vca_row(**{"Fuel Type": label})]))
    assert db.query(CatalogVehicle).one().fuel_type == expected


def test_unknown_fuel_is_skipped(db):
    vca_catalog.ingest(db, data=build_zip([vca_row(**{"Fuel Type": "Hydrogen"})]))
    assert db.query(CatalogVehicle).count() == 0


def test_attribution_recorded(db):
    vca_catalog.ingest(db, data=build_zip())
    row = db.query(CatalogVehicle).one()
    assert row.source == CatalogSource.vca
    assert row.licence == "Crown copyright"


def test_import_is_idempotent(db):
    data = build_zip()
    assert vca_catalog.ingest(db, data=data).inserted == 1
    second = vca_catalog.ingest(db, data=data)
    assert second.inserted == 0 and second.updated == 0
    assert db.query(CatalogVehicle).count() == 1


# --- locating the file --------------------------------------------------------

def test_data_dir_falls_back_to_the_container_layout(tmp_path, monkeypatch):
    """The repo keeps data/ beside the backend, the image copies it inside.
    Only the second exists in production, and it was silently unreachable."""
    container = tmp_path / "app" / "data" / "vca"
    container.mkdir(parents=True)
    monkeypatch.setattr(
        vca_catalog, "DATA_DIR_CANDIDATES", (tmp_path / "nonexistent", container)
    )
    assert vca_catalog.data_dir() == container


def test_data_dir_override_wins(tmp_path, monkeypatch):
    elsewhere = tmp_path / "mounted"
    elsewhere.mkdir()
    monkeypatch.setattr(vca_catalog.settings, "vca_data_dir", str(elsewhere))
    assert vca_catalog.data_dir() == elsewhere


def test_missing_data_dir_lists_what_was_tried(tmp_path, monkeypatch):
    monkeypatch.setattr(
        vca_catalog, "DATA_DIR_CANDIDATES", (tmp_path / "a", tmp_path / "b")
    )
    with pytest.raises(FileNotFoundError, match="tried:"):
        vca_catalog.data_dir()


def test_missing_csv_in_zip_is_reported():
    empty = io.BytesIO()
    with zipfile.ZipFile(empty, "w") as z:
        z.writestr("readme.txt", "nothing here")
    with pytest.raises(ValueError, match="no CSV"):
        vca_catalog.read_rows(empty.getvalue())


# --- the source disagrees with itself ----------------------------------------

@pytest.mark.parametrize(
    "description,expected",
    [
        ("iconic 150 hp comfort range", 150),
        ("evolution 120 hp urban range", 120),
        ("techno TCe 90", None),          # no explicit "hp"
        ("320i M Sport", None),           # a bare number is not power
        ("", None),
    ],
)
def test_power_stated_in_the_trim_name(description, expected):
    assert vca_catalog.stated_power(description) == expected


def test_trim_name_wins_when_the_declared_power_disagrees(db):
    """A pure EV has no engine/system distinction, so 120 vs 150 is an error:
    the row carries the 40 kWh car's 301 km range."""
    vca_catalog.ingest(db, data=build_zip([
        vca_row(Description="evolution 120 hp urban range",
                **{"Engine Power (PS)": "150", "Maximum range (Km)": "301"}),
    ]))
    row = db.query(CatalogVehicle).one()
    assert row.horsepower == 120
    assert "differs" in row.data_quality        # the conflict is visible


def test_hybrid_system_power_is_kept_over_engine_power(db):
    """Most conflicts are hybrids quoting system power in the name and engine
    power in the column. Both are right; total output is the useful one."""
    vca_catalog.ingest(db, data=build_zip([
        vca_row(Description="Hybrid 145hp automatic",
                **{"Fuel Type": "Petrol Electric", "Engine Capacity": "1199",
                   "Engine Power (PS)": "136", "WLTP Metric Combined": "4.5"}),
    ]))
    row = db.query(CatalogVehicle).one()
    assert row.horsepower == 145                # system, not the 136 engine PS
    assert row.fuel_type == FuelType.hybrid


def test_small_differences_are_not_treated_as_conflicts(db):
    """"TCe 90" declaring 91 PS is rounding, not a mistake."""
    vca_catalog.ingest(db, data=build_zip([
        vca_row(Description="techno 90 hp", **{"Engine Power (PS)": "91"}),
    ]))
    row = db.query(CatalogVehicle).one()
    assert row.horsepower == 91                 # the declared figure stands
    assert row.data_quality == "manufacturer declared"


def test_the_same_car_described_two_ways_is_one_entry(db):
    """The source writes the model into some Description fields and not others.
    Both clean to the same trim, so they showed as identical entries in the
    picker while hashing to two different ids."""
    # The Model column carries the make for some marques, exactly as here.
    rows = [
        vca_row(Model="Mazda CX-60", Description="Mazda CX-60 2.5 327ps AWD Exclusive"),
        vca_row(Model="Mazda CX-60", Description="2.5 327ps AWD Exclusive"),
    ]
    vca_catalog.ingest(db, data=build_zip(rows))
    assert db.query(CatalogVehicle).count() == 1


def test_rows_the_file_no_longer_describes_are_dropped(db):
    """An import that only ever adds leaves the catalogue full of cars no
    source still lists — including rows left behind by an older id scheme."""
    vca_catalog.ingest(db, data=build_zip([
        vca_row(Model="Old", Description="discontinued"),
        vca_row(Model="Kept", Description="still sold"),
    ]))
    assert db.query(CatalogVehicle).count() == 2

    vca_catalog.ingest(db, data=build_zip([
        vca_row(Model="Kept", Description="still sold"),
    ]))
    assert [c.model for c in db.query(CatalogVehicle).all()] == ["Kept"]


def test_a_truncated_file_cannot_empty_the_catalogue(db):
    """A half-downloaded file should not look like "everything was retired"."""
    vca_catalog.ingest(db, data=build_zip([
        vca_row(Model=f"Model {i}", Description=f"trim {i}") for i in range(10)
    ]))
    assert db.query(CatalogVehicle).count() == 10

    vca_catalog.ingest(db, data=build_zip([vca_row(Model="Model 0", Description="trim 0")]))
    assert db.query(CatalogVehicle).count() == 10        # nothing pruned
