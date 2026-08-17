import datetime
from pydantic import BaseModel, Field, model_validator
from app.models.fuel_event import ChargerType, DrivingMix


class FuelEventBase(BaseModel):
    vehicle_id: int
    date: datetime.date
    time_of_day: datetime.time | None = None

    odometer_km: float = Field(ge=0)

    # What went in. A charge fills the first, a tank of fuel the second, and a
    # plug-in hybrid can fill both on one stop — so neither is required alone,
    # but an event that recorded nothing going in would be meaningless.
    energy_kwh: float | None = Field(default=None, gt=0)
    volume_litres: float | None = Field(default=None, gt=0)

    cost: float | None = Field(default=None, ge=0)
    currency: str = "EUR"

    soc_start_pct: float | None = Field(default=None, ge=0, le=100)
    soc_end_pct: float | None = Field(default=None, ge=0, le=100)
    tank_start_pct: float | None = Field(default=None, ge=0, le=100)
    tank_end_pct: float | None = Field(default=None, ge=0, le=100)

    charger_type: ChargerType | None = None
    charger_capacity_kw: float | None = Field(default=None, gt=0)

    location_city: str | None = None
    country: str = "IE"

    driving_mix: DrivingMix | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def check_something_went_in(self):
        if self.energy_kwh is None and self.volume_litres is None:
            raise ValueError(
                "Record what went in: energy_kwh, volume_litres, or both for a "
                "plug-in hybrid"
            )
        return self

    @model_validator(mode="after")
    def check_levels(self):
        for start, end, name in (
            (self.soc_start_pct, self.soc_end_pct, "soc"),
            (self.tank_start_pct, self.tank_end_pct, "tank"),
        ):
            if (start is None) != (end is None):
                raise ValueError(
                    f"{name}_start_pct and {name}_end_pct must be given together "
                    "(both or neither) — one alone cannot describe a fill"
                )
            if start is not None and end is not None and end <= start:
                raise ValueError(f"{name}_end_pct must be greater than {name}_start_pct")
        return self


class FuelEventCreate(FuelEventBase):
    pass


class FuelEventUpdate(FuelEventBase):
    pass


class FuelEventRead(FuelEventBase):
    id: int

    model_config = {"from_attributes": True}
