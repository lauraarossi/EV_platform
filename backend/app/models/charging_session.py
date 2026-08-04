import enum
import datetime
from sqlalchemy import String, Float, Integer, ForeignKey, Date, Time, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class ChargerType(str, enum.Enum):
    ac_home = "ac_home"
    ac_public = "ac_public"
    dc_rapid = "dc_rapid"
    dc_ultra = "dc_ultra"


class ChargingSession(Base, TimestampMixin):
    __tablename__ = "charging_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    trip_id: Mapped[int | None] = mapped_column(ForeignKey("trips.id"), nullable=True, index=True)

    date: Mapped[datetime.date] = mapped_column(Date, index=True)
    time_of_day: Mapped[datetime.time | None] = mapped_column(Time)

    kwh_charged: Mapped[float] = mapped_column(Float)
    cost: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    charger_type: Mapped[ChargerType] = mapped_column(Enum(ChargerType))
    charger_capacity_kw: Mapped[float | None] = mapped_column(Float)

    location_city: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(10), default="IE")

    vehicle: Mapped["Vehicle"] = relationship(back_populates="charging_sessions")
    trip: Mapped["Trip | None"] = relationship(back_populates="charging_sessions")
