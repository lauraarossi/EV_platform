import datetime

from sqlalchemy import String, Float, Integer, Date, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ExchangeRate(Base, TimestampMixin):
    """One currency's rate against the base, on one day.

    Stored as a series rather than a single current figure, for the same reason
    fuel prices are: a charge from March should be converted at March's rate,
    not at this week's. Sterling moved 1% against the euro in the month these
    were first fetched, which is enough to make a year of history wrong.

    The base is the euro throughout, because the source publishes against it
    and because everything else in here is already euro-denominated.
    """

    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint("date", "base", "quote", name="uq_exchange_rate_point"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    date: Mapped[datetime.date] = mapped_column(Date, index=True)
    base: Mapped[str] = mapped_column(String(3), default="EUR", index=True)
    quote: Mapped[str] = mapped_column(String(3), index=True)
    # How many of `quote` one unit of `base` buys.
    rate: Mapped[float] = mapped_column(Float)
