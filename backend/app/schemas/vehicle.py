from pydantic import BaseModel, Field
from app.models.vehicle import FuelType, Transmission


class VehicleBase(BaseModel):
    make: str
    model: str
    trim: str | None = None
    year: int
    fuel_type: FuelType = FuelType.electric
    transmission: Transmission | None = None
    nickname: str | None = None
    image_url: str | None = None

    battery_capacity_kwh: float | None = Field(default=None, gt=0)
    onboard_charger_kw: float | None = Field(default=None, gt=0)
    wltp_range_km: float | None = Field(default=None, gt=0)

    engine_size_cc: int | None = Field(default=None, gt=0)
    fuel_consumption_l_per_100km: float | None = Field(default=None, gt=0)

    horsepower: int | None = Field(default=None, gt=0)
    zero_to_100_seconds: float | None = Field(default=None, gt=0)
    top_speed_kmh: int | None = Field(default=None, gt=0)
    kerb_weight_kg: int | None = Field(default=None, gt=0)

    is_comparison_vehicle: bool = False


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(VehicleBase):
    pass


class VehicleRead(VehicleBase):
    id: int

    model_config = {"from_attributes": True}
