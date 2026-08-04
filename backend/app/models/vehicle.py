import enum
import datetime
from sqlalchemy import String, Float, Integer, Enum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class FuelType(str, enum.Enum):
    electric = "electric"
    petrol = "petrol"
    diesel = "diesel"
    hybrid = "hybrid"


class Vehicle(Base, TimestampMixin):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    make: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    trim: Mapped[str | None] = mapped_column(String(100))
    year: Mapped[int] = mapped_column(Integer)
    fuel_type: Mapped[FuelType] = mapped_column(Enum(FuelType), default=FuelType.electric)

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

    trips: Mapped[list["Trip"]] = relationship(back_populates="vehicle")
    charging_sessions: Mapped[list["ChargingSession"]] = relationship(back_populates="vehicle")
