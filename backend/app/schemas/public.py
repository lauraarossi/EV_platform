"""What the signed-out tools send and receive.

Nothing here is stored. A visitor's cars and fill-ups live in their browser;
these carry them to the server, which does the arithmetic and returns it. The
alternative — reimplementing consumption, pricing and emissions in TypeScript
— would leave two versions of the same rules to drift apart, and the whole
point of the comparison is that its rules are consistent.
"""

import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.fuel_event import ChargerType, DrivingMix, FuelEvent
from app.models.vehicle import FuelType, Vehicle


class VehicleSpec(BaseModel):
    """A car described in a request rather than looked up by id."""

    make: str = Field(default="Car", max_length=100)
    model: str = Field(default="", max_length=100)
    nickname: str | None = Field(default=None, max_length=100)
    fuel_type: FuelType

    consumption_kwh_per_100km: float | None = Field(default=None, gt=0)
    battery_capacity_kwh: float | None = Field(default=None, gt=0)
    wltp_range_km: float | None = Field(default=None, gt=0)

    fuel_consumption_l_per_100km: float | None = Field(default=None, gt=0)
    tank_capacity_litres: float | None = Field(default=None, gt=0)

    def as_vehicle(self, vehicle_id: int = 0) -> Vehicle:
        """An unsaved Vehicle, so the same services can read it.

        Never added to a session — the services only read attributes off it,
        which is what makes a signed-out comparison possible at all.
        """
        return Vehicle(
            id=vehicle_id,
            make=self.make,
            model=self.model,
            nickname=self.nickname,
            year=0,
            fuel_type=self.fuel_type,
            consumption_kwh_per_100km=self.consumption_kwh_per_100km,
            battery_capacity_kwh=self.battery_capacity_kwh,
            wltp_range_km=self.wltp_range_km,
            fuel_consumption_l_per_100km=self.fuel_consumption_l_per_100km,
            tank_capacity_litres=self.tank_capacity_litres,
        )


class PublicEvent(BaseModel):
    """A fill-up held in a browser, with no vehicle id to belong to."""

    date: datetime.date
    time_of_day: datetime.time | None = None
    odometer_km: float = Field(ge=0)

    energy_kwh: float | None = Field(default=None, gt=0)
    volume_litres: float | None = Field(default=None, gt=0)
    cost: float | None = Field(default=None, ge=0)

    soc_start_pct: float | None = Field(default=None, ge=0, le=100)
    soc_end_pct: float | None = Field(default=None, ge=0, le=100)
    tank_start_pct: float | None = Field(default=None, ge=0, le=100)
    tank_end_pct: float | None = Field(default=None, ge=0, le=100)

    charger_type: ChargerType | None = None
    driving_mix: DrivingMix | None = None
    location_city: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def check_something_went_in(self):
        if self.energy_kwh is None and self.volume_litres is None:
            raise ValueError("Record what went in: energy_kwh, volume_litres, or both")
        return self

    def as_event(self, event_id: int) -> FuelEvent:
        return FuelEvent(
            id=event_id,
            vehicle_id=0,
            date=self.date,
            time_of_day=self.time_of_day,
            odometer_km=self.odometer_km,
            energy_kwh=self.energy_kwh,
            volume_litres=self.volume_litres,
            cost=self.cost,
            soc_start_pct=self.soc_start_pct,
            soc_end_pct=self.soc_end_pct,
            tank_start_pct=self.tank_start_pct,
            tank_end_pct=self.tank_end_pct,
            charger_type=self.charger_type,
            driving_mix=self.driving_mix,
            location_city=self.location_city,
        )


# A visitor can only send so much before this stops being a calculator and
# starts being a way to make the server work for free.
MAX_EVENTS = 500


class MetricsRequest(BaseModel):
    vehicle: VehicleSpec
    events: list[PublicEvent] = Field(default_factory=list, max_length=MAX_EVENTS)


class CompareRequest(BaseModel):
    first: VehicleSpec
    second: VehicleSpec

    # Either a distance to model, or a log to measure one from. A log also
    # supplies what was actually paid, which beats any quoted rate.
    distance_km: float | None = Field(default=None, gt=0)
    events: list[PublicEvent] = Field(default_factory=list, max_length=MAX_EVENTS)

    # Shown in the form and editable, because a signed-out visitor has no
    # tariff and no receipts, and a fixed national average is wrong for anyone
    # on a night rate.
    price_per_litre: float | None = Field(default=None, gt=0)
    price_per_kwh: float | None = Field(default=None, gt=0)

    measured_weight: float = Field(default=0.0, ge=0, le=1)
    apply_gap_to_alternative: bool = False

    @model_validator(mode="after")
    def check_there_is_something_to_measure(self):
        if self.distance_km is None and len(self.events) < 2:
            raise ValueError(
                "Give a distance_km, or at least two events to derive one from"
            )
        return self
