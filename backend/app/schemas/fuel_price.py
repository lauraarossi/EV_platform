import datetime
from pydantic import BaseModel, Field
from app.models.fuel_price import FuelKind, PriceSource


class FuelPriceBase(BaseModel):
    date: datetime.date
    country: str = "IE"
    region: str = Field(default="", description="Empty means the national average")
    fuel_kind: FuelKind = FuelKind.petrol_95
    price_per_litre: float = Field(gt=0)
    currency: str = "EUR"


class FuelPriceCreate(FuelPriceBase):
    """User-entered prices are always recorded as manual, so a re-ingest of the
    Oil Bulletin can never overwrite them."""


class FuelPriceRead(FuelPriceBase):
    id: int
    source: PriceSource

    model_config = {"from_attributes": True}


class PriceQuoteRead(BaseModel):
    price_per_litre: float
    as_of: datetime.date
    source: PriceSource
    region: str
    staleness_days: int
