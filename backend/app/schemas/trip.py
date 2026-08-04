import datetime
from pydantic import BaseModel


class TripBase(BaseModel):
    vehicle_id: int
    date: datetime.date
    distance_km: float
    average_speed_kmh: float | None = None
    origin_city: str | None = None
    destination_city: str | None = None
    country: str = "IE"
    notes: str | None = None


class TripCreate(TripBase):
    pass


class TripUpdate(TripBase):
    pass


class TripRead(TripBase):
    id: int

    model_config = {"from_attributes": True}
