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

    # Electric side. Battery capacity turns a state-of-charge swing into kWh.
    battery_capacity_kwh: Mapped[float | None] = mapped_column(Float)
    onboard_charger_kw: Mapped[float | None] = mapped_column(Float)
    wltp_range_km: Mapped[float | None] = mapped_column(Float)
    # Quoted consumption, used to price this car as a hypothetical alternative.
    consumption_kwh_per_100km: Mapped[float | None] = mapped_column(Float)

    # Liquid-fuel side, mirroring the two above: tank capacity turns a tank
    # percentage into litres, and the quoted figure prices the car hypothetically.
    engine_size_cc: Mapped[int | None] = mapped_column(Integer)
    tank_capacity_litres: Mapped[float | None] = mapped_column(Float)
    fuel_consumption_l_per_100km: Mapped[float | None] = mapped_column(Float)

    # Performance (shared)
    horsepower: Mapped[int | None] = mapped_column(Integer)
    zero_to_100_seconds: Mapped[float | None] = mapped_column(Float)
    top_speed_kmh: Mapped[int | None] = mapped_column(Integer)
    kerb_weight_kg: Mapped[int | None] = mapped_column(Integer)

    # A car you do not own, kept only to price your driving against. Any fuel
    # type can sit on either side: an EV owner comparing against petrol, or a
    # diesel owner wondering what an EV would have cost.
    is_comparison_vehicle: Mapped[bool] = mapped_column(default=False)

    nickname: Mapped[str | None] = mapped_column(String(100))
    # Remote URL rather than an upload: PaaS filesystems are ephemeral, so
    # storing bytes locally would lose the image on every redeploy.
    image_url: Mapped[str | None] = mapped_column(String(500))

    user: Mapped["User"] = relationship(back_populates="vehicles")
    fuel_events: Mapped[list["FuelEvent"]] = relationship(
        back_populates="vehicle", cascade="all, delete-orphan"
    )
