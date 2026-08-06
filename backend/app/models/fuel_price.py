import enum
import datetime
from sqlalchemy import String, Float, Integer, Date, Enum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class FuelKind(str, enum.Enum):
    petrol_95 = "petrol_95"
    diesel = "diesel"


class PriceSource(str, enum.Enum):
    # European Commission Weekly Oil Bulletin — national averages, weekly.
    eu_oil_bulletin = "eu_oil_bulletin"
    # Anything the user typed in themselves, which always wins over a feed.
    manual = "manual"


class FuelPrice(Base, TimestampMixin):
    """A pump price for one fuel, on one date, for one place.

    `region` carries the geographic granularity: an empty string means the
    national average, anything else is a city (and later, potentially a named
    station). Storing it this way keeps a plain unique constraint usable while
    still letting finer-grained sources slot in later without a schema change.
    """

    __tablename__ = "fuel_prices"
    __table_args__ = (
        UniqueConstraint(
            "date", "country", "region", "fuel_kind", "source", name="uq_fuel_price_point"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    date: Mapped[datetime.date] = mapped_column(Date, index=True)
    country: Mapped[str] = mapped_column(String(2), index=True)
    region: Mapped[str] = mapped_column(String(100), default="", index=True)

    fuel_kind: Mapped[FuelKind] = mapped_column(Enum(FuelKind), index=True)
    price_per_litre: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    source: Mapped[PriceSource] = mapped_column(Enum(PriceSource), index=True)
