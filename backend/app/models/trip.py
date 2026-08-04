import datetime
from sqlalchemy import String, Float, Integer, ForeignKey, Date, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class Trip(Base, TimestampMixin):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    date: Mapped[datetime.date] = mapped_column(Date, index=True)

    distance_km: Mapped[float] = mapped_column(Float)
    average_speed_kmh: Mapped[float | None] = mapped_column(Float)

    origin_city: Mapped[str | None] = mapped_column(String(100))
    destination_city: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(10), default="IE")

    notes: Mapped[str | None] = mapped_column(Text)

    vehicle: Mapped["Vehicle"] = relationship(back_populates="trips")
    charging_sessions: Mapped[list["ChargingSession"]] = relationship(back_populates="trip")
