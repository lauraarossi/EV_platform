import enum
import datetime
from sqlalchemy import String, Float, Integer, ForeignKey, Date, Time, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class ChargerType(str, enum.Enum):
    ac_home = "ac_home"
    ac_public = "ac_public"
    dc_rapid = "dc_rapid"
    dc_ultra = "dc_ultra"


class DrivingMix(str, enum.Enum):
    city = "city"
    mixed = "mixed"
    motorway = "motorway"


class ChargingSession(Base, TimestampMixin):
    """One charge event, plus the odometer reading at that moment.

    Distance and energy are never stored — they are derived from consecutive
    sessions (see app.services.metrics). The odometer closes off the interval
    since the previous charge; the SoC pair makes the energy figure exact even
    when charge targets vary (80% one time, 100% the next).
    """

    __tablename__ = "charging_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)

    date: Mapped[datetime.date] = mapped_column(Date, index=True)
    time_of_day: Mapped[datetime.time | None] = mapped_column(Time)

    # Distance side
    odometer_km: Mapped[float] = mapped_column(Float)

    # Money side
    kwh_added: Mapped[float] = mapped_column(Float)
    cost: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    # Energy side — optional; when both are present the efficiency for the
    # preceding interval is exact rather than approximated from kwh_added.
    soc_start_pct: Mapped[float | None] = mapped_column(Float)
    soc_end_pct: Mapped[float | None] = mapped_column(Float)

    charger_type: Mapped[ChargerType] = mapped_column(Enum(ChargerType))
    charger_capacity_kw: Mapped[float | None] = mapped_column(Float)

    location_city: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(10), default="IE")

    driving_mix: Mapped[DrivingMix | None] = mapped_column(Enum(DrivingMix))
    notes: Mapped[str | None] = mapped_column(Text)

    vehicle: Mapped["Vehicle"] = relationship(back_populates="charging_sessions")
