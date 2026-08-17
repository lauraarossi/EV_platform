import enum
import datetime
from sqlalchemy import String, Float, Integer, ForeignKey, Date, Time, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class ChargerType(str, enum.Enum):
    """How an electric charge was taken. Null for a liquid-fuel fill-up."""

    ac_home = "ac_home"
    ac_public = "ac_public"
    dc_rapid = "dc_rapid"
    dc_ultra = "dc_ultra"


class DrivingMix(str, enum.Enum):
    city = "city"
    mixed = "mixed"
    motorway = "motorway"


class FuelEvent(Base, TimestampMixin):
    """One refuelling — a charge, a tank of petrol, or both — plus the odometer
    reading at that moment.

    Distance and consumption are never stored: they are derived from pairs of
    consecutive events (see app.services.metrics). The odometer closes off the
    interval since the last one.

    The same shape covers every fuel. What went in is always recorded, because
    that is what was paid for. The level either side is optional, and is what
    makes consumption exact rather than approximate — the classic method
    ("what went in is what came out") only holds if you refill to the same
    level every time, which nobody does: EV owners charge to 80% and sometimes
    100%, and a driver puts in €30 rather than a full tank.

    Battery and tank levels are separate pairs rather than one generic "level",
    because a plug-in hybrid takes both and a single figure could not say which
    it described.
    """

    __tablename__ = "fuel_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)

    date: Mapped[datetime.date] = mapped_column(Date, index=True)
    time_of_day: Mapped[datetime.time | None] = mapped_column(Time)

    # Distance side
    odometer_km: Mapped[float] = mapped_column(Float)

    # What went in. A pure EV fills the first, a petrol car the second, and a
    # plug-in hybrid can fill both on the same stop.
    energy_kwh: Mapped[float | None] = mapped_column(Float)
    volume_litres: Mapped[float | None] = mapped_column(Float)

    cost: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    # Levels either side, as percentages. Optional; when present the preceding
    # interval's consumption is exact rather than inferred from what went in.
    soc_start_pct: Mapped[float | None] = mapped_column(Float)
    soc_end_pct: Mapped[float | None] = mapped_column(Float)
    tank_start_pct: Mapped[float | None] = mapped_column(Float)
    tank_end_pct: Mapped[float | None] = mapped_column(Float)

    # Electric only.
    charger_type: Mapped[ChargerType | None] = mapped_column(Enum(ChargerType))
    charger_capacity_kw: Mapped[float | None] = mapped_column(Float)

    location_city: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(10), default="IE")

    driving_mix: Mapped[DrivingMix | None] = mapped_column(Enum(DrivingMix))
    notes: Mapped[str | None] = mapped_column(Text)

    vehicle: Mapped["Vehicle"] = relationship(back_populates="fuel_events")
