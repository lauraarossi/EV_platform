import datetime
from sqlalchemy import String, Float, Integer, Date, Time, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class ElectricityTariff(Base, TimestampMixin):
    """One version of an electricity tariff, valid over a date range.

    Tariffs are versioned rather than edited: when your rates change you add a
    new version with a new `effective_from`, and the previous version is closed
    off. That keeps historical charges priced at the rate that actually applied
    at the time, instead of retroactively rewriting them.
    """

    __tablename__ = "electricity_tariffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    supplier: Mapped[str | None] = mapped_column(String(120))

    effective_from: Mapped[datetime.date] = mapped_column(Date, index=True)
    # NULL means "still current" — exactly one version should be open at a time.
    effective_to: Mapped[datetime.date | None] = mapped_column(Date, index=True)

    standing_charge_per_day: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    user: Mapped["User"] = relationship(back_populates="tariffs")
    rates: Mapped[list["TariffRate"]] = relationship(
        back_populates="tariff", cascade="all, delete-orphan", order_by="TariffRate.start_time"
    )


class TariffRate(Base, TimestampMixin):
    """A price band within a tariff, e.g. Night 23:00–08:00 at €0.17/kWh.

    A band may wrap past midnight (start_time > end_time); the lookup handles
    that rather than requiring the user to split it into two rows.
    """

    __tablename__ = "tariff_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tariff_id: Mapped[int] = mapped_column(
        ForeignKey("electricity_tariffs.id", ondelete="CASCADE"), index=True
    )

    name: Mapped[str] = mapped_column(String(60))
    start_time: Mapped[datetime.time] = mapped_column(Time)
    end_time: Mapped[datetime.time] = mapped_column(Time)
    price_per_kwh: Mapped[float] = mapped_column(Float)

    tariff: Mapped["ElectricityTariff"] = relationship(back_populates="rates")
