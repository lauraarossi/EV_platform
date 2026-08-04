from pydantic import BaseModel
from app.models.vehicle import FuelType


class VehicleBase(BaseModel):
    make: str
    model: str
    trim: str | None = None
    year: int
    fuel_type: FuelType = FuelType.electric
    battery_capacity_kwh: float | None = None
    onboard_charger_kw: float | None = None
    wltp_range_km: float | None = None
    engine_size_cc: int | None = None
    fuel_consumption_l_per_100km: float | None = None
    horsepower: int | None = None
    zero_to_100_seconds: float | None = None
    top_speed_kmh: int | None = None
    kerb_weight_kg: int | None = None
    is_comparison_vehicle: bool = False


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(VehicleBase):
    pass


class VehicleRead(VehicleBase):
    id: int

    model_config = {"from_attributes": True}
