import datetime
from pydantic import BaseModel, Field, model_validator
from app.models.charging_session import ChargerType, DrivingMix


class ChargingSessionBase(BaseModel):
    vehicle_id: int
    date: datetime.date
    time_of_day: datetime.time | None = None

    odometer_km: float = Field(ge=0)
    kwh_added: float = Field(gt=0)
    cost: float | None = Field(default=None, ge=0)
    currency: str = "EUR"

    soc_start_pct: float | None = Field(default=None, ge=0, le=100)
    soc_end_pct: float | None = Field(default=None, ge=0, le=100)

    charger_type: ChargerType
    charger_capacity_kw: float | None = Field(default=None, gt=0)

    location_city: str | None = None
    country: str = "IE"

    driving_mix: DrivingMix | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def check_soc(self):
        s, e = self.soc_start_pct, self.soc_end_pct
        if (s is None) != (e is None):
            raise ValueError(
                "soc_start_pct and soc_end_pct must be provided together "
                "(both or neither) — one alone cannot describe a charge"
            )
        if s is not None and e is not None and e <= s:
            raise ValueError("soc_end_pct must be greater than soc_start_pct")
        return self


class ChargingSessionCreate(ChargingSessionBase):
    pass


class ChargingSessionUpdate(ChargingSessionBase):
    pass


class ChargingSessionRead(ChargingSessionBase):
    id: int

    model_config = {"from_attributes": True}
