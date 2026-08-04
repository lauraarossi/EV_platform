import datetime
from pydantic import BaseModel
from app.models.charging_session import ChargerType


class ChargingSessionBase(BaseModel):
    vehicle_id: int
    trip_id: int | None = None
    date: datetime.date
    time_of_day: datetime.time | None = None
    kwh_charged: float
    cost: float | None = None
    currency: str = "EUR"
    charger_type: ChargerType
    charger_capacity_kw: float | None = None
    location_city: str | None = None
    country: str = "IE"


class ChargingSessionCreate(ChargingSessionBase):
    pass


class ChargingSessionUpdate(ChargingSessionBase):
    pass


class ChargingSessionRead(ChargingSessionBase):
    id: int

    model_config = {"from_attributes": True}
