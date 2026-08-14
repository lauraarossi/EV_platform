import enum
import datetime
from sqlalchemy import String, Float, Integer, Enum, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class FuelType(str, enum.Enum):
    electric = "electric"
    petrol = "petrol"
    diesel = "diesel"
    hybrid = "hybrid"


class Transmission(str, enum.Enum):
    """Common transmissions, offered as suggestions rather than enforced.

    The column is free text: no catalogue we ingest records a transmission at
    all, so anything stored here is typed by a person, and real gearboxes are
    messier than a fixed list ("7-speed DSG", "e-CVT", "single-speed reduction
    gear"). These values just populate the dropdown.
    """

    single_speed = "single_speed"
    manual = "manual"
    automatic = "automatic"
    cvt = "cvt"
    dual_clutch = "dual_clutch"


class Vehicle(Base, TimestampMixin):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    make: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    trim: Mapped[str | None] = mapped_column(String(100))
    year: Mapped[int] = mapped_column(Integer)
    fuel_type: Mapped[FuelType] = mapped_column(Enum(FuelType), default=FuelType.electric)
    # Free text, not an enum: see Transmission's docstring.
    transmission: Mapped[str | None] = mapped_column(String(60))

    # EV-specific
    battery_capacity_kwh: Mapped[float | None] = mapped_column(Float)
    onboard_charger_kw: Mapped[float | None] = mapped_column(Float)
    wltp_range_km: Mapped[float | None] = mapped_column(Float)

    # Petrol comparison car fields
    engine_size_cc: Mapped[int | None] = mapped_column(Integer)
    fuel_consumption_l_per_100km: Mapped[float | None] = mapped_column(Float)

    # Performance (shared)
    horsepower: Mapped[int | None] = mapped_column(Integer)
    zero_to_100_seconds: Mapped[float | None] = mapped_column(Float)
    top_speed_kmh: Mapped[int | None] = mapped_column(Integer)
    kerb_weight_kg: Mapped[int | None] = mapped_column(Integer)

    is_comparison_vehicle: Mapped[bool] = mapped_column(default=False)

    nickname: Mapped[str | None] = mapped_column(String(100))
    # Remote URL rather than an upload: PaaS filesystems are ephemeral, so
    # storing bytes locally would lose the image on every redeploy.
    image_url: Mapped[str | None] = mapped_column(String(500))

    user: Mapped["User"] = relationship(back_populates="vehicles")
    charging_sessions: Mapped[list["ChargingSession"]] = relationship(
        back_populates="vehicle", cascade="all, delete-orphan"
    )
