import enum
from sqlalchemy import String, Float, Integer, Enum, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin
from app.models.vehicle import FuelType, Transmission


class CatalogSource(str, enum.Enum):
    evdb = "evdb"
    # EEA CO2 monitoring (Regulation EU 2019/631): every new car registered in
    # the EU. Covers combustion as well as electric, which evdb does not.
    eea = "eea"
    manual = "manual"


class CatalogVehicle(Base, TimestampMixin):
    """A vehicle specification from a reference catalogue.

    Kept deliberately separate from `vehicles`: this is third-party reference
    data used to *prefill* a car you own, and refreshing it must never
    overwrite figures you have corrected yourself. It also keeps the licensing
    boundary clean, since catalogue rows carry their own attribution.
    """

    __tablename__ = "catalog_vehicles"
    __table_args__ = (Index("ix_catalog_make_model", "make", "model"),)

    # Stable id from the source (e.g. 'renault-4-e-tech-techno-52-2025') so a
    # refresh updates rows in place rather than duplicating them.
    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    source: Mapped[CatalogSource] = mapped_column(Enum(CatalogSource), index=True)
    source_name: Mapped[str | None] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(300))
    licence: Mapped[str | None] = mapped_column(String(60))

    make: Mapped[str] = mapped_column(String(100), index=True)
    model: Mapped[str] = mapped_column(String(120), index=True)
    variant: Mapped[str] = mapped_column(String(200))
    model_year: Mapped[int | None] = mapped_column(Integer, index=True)

    fuel_type: Mapped[FuelType] = mapped_column(Enum(FuelType), index=True)
    # Free text to match vehicles.transmission; no source records this.
    transmission: Mapped[str | None] = mapped_column(String(60))

    # EV
    battery_capacity_kwh: Mapped[float | None] = mapped_column(Float)
    battery_usable_kwh: Mapped[float | None] = mapped_column(Float)
    onboard_charger_kw: Mapped[float | None] = mapped_column(Float)
    dc_charge_power_kw: Mapped[float | None] = mapped_column(Float)
    wltp_range_km: Mapped[float | None] = mapped_column(Float)
    consumption_wltp_kwh_100km: Mapped[float | None] = mapped_column(Float)
    # A third benchmark to hold your measured efficiency against.
    consumption_real_world_kwh_100km: Mapped[float | None] = mapped_column(Float)

    # Combustion
    engine_size_cc: Mapped[int | None] = mapped_column(Integer)
    fuel_consumption_l_per_100km: Mapped[float | None] = mapped_column(Float)

    # Shared performance
    horsepower: Mapped[int | None] = mapped_column(Integer)
    zero_to_100_seconds: Mapped[float | None] = mapped_column(Float)
    top_speed_kmh: Mapped[int | None] = mapped_column(Integer)
    kerb_weight_kg: Mapped[int | None] = mapped_column(Integer)

    body_style: Mapped[str | None] = mapped_column(String(60))
    image_url: Mapped[str | None] = mapped_column(String(500))
    data_quality: Mapped[str | None] = mapped_column(String(40))

    # Market this row describes (EEA rows are per member state). Lets the
    # picker prefer cars actually sold here.
    country: Mapped[str | None] = mapped_column(String(2), index=True)
    # How many of these were registered — a popularity signal, so common cars
    # sort to the top rather than being buried among rare variants.
    registration_count: Mapped[int | None] = mapped_column(Integer)
    # Set when EV detail (battery, range) was copied in from another catalogue
    # row, so the provenance of a merged record stays visible.
    enriched_from: Mapped[str | None] = mapped_column(String(160))
