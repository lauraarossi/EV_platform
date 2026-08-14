from pydantic import BaseModel
from app.models.catalog import CatalogSource
from app.models.vehicle import FuelType, Transmission


class CatalogMake(BaseModel):
    make: str
    model_count: int


class CatalogModel(BaseModel):
    make: str
    model: str
    variant_count: int


class CatalogVehicleRead(BaseModel):
    id: str
    source: CatalogSource
    source_name: str | None
    source_url: str | None
    licence: str | None

    make: str
    model: str
    variant: str
    model_year: int | None

    fuel_type: FuelType
    transmission: Transmission | None

    battery_capacity_kwh: float | None
    battery_usable_kwh: float | None
    onboard_charger_kw: float | None
    dc_charge_power_kw: float | None
    wltp_range_km: float | None
    consumption_wltp_kwh_100km: float | None
    consumption_real_world_kwh_100km: float | None

    engine_size_cc: int | None
    fuel_consumption_l_per_100km: float | None

    horsepower: int | None
    zero_to_100_seconds: float | None
    top_speed_kmh: int | None
    kerb_weight_kg: int | None

    body_style: str | None
    image_url: str | None
    data_quality: str | None
    country: str | None
    registration_count: int | None
    enriched_from: str | None

    model_config = {"from_attributes": True, "protected_namespaces": ()}
