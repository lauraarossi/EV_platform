import datetime
from pydantic import BaseModel, Field, model_validator


class TariffRateBase(BaseModel):
    name: str
    start_time: datetime.time
    end_time: datetime.time
    price_per_kwh: float = Field(ge=0)


class TariffRateRead(TariffRateBase):
    id: int
    model_config = {"from_attributes": True}


class TariffBase(BaseModel):
    name: str
    supplier: str | None = None
    effective_from: datetime.date
    effective_to: datetime.date | None = None
    standing_charge_per_day: float | None = Field(default=None, ge=0)
    currency: str = "EUR"

    @model_validator(mode="after")
    def check_dates(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be before effective_from")
        return self


class TariffCreate(TariffBase):
    rates: list[TariffRateBase] = Field(min_length=1)

    @model_validator(mode="after")
    def check_rates(self):
        # A flat tariff is one band; a day/night tariff is two. Overlapping
        # bands would make the rate for a given time ambiguous.
        spans: list[tuple[datetime.time, datetime.time]] = []
        for r in self.rates:
            for s, e in spans:
                if _overlaps((r.start_time, r.end_time), (s, e)):
                    raise ValueError(f"rate band '{r.name}' overlaps another band")
            spans.append((r.start_time, r.end_time))
        return self


class TariffUpdate(TariffCreate):
    pass


class TariffRead(TariffBase):
    id: int
    rates: list[TariffRateRead]
    model_config = {"from_attributes": True}


class RateQuoteRead(BaseModel):
    tariff_id: int
    tariff_name: str
    rate_name: str
    price_per_kwh: float
    exact: bool
    """False when no time of day was given and the cheapest band was assumed."""


def _minutes(t: datetime.time) -> int:
    return t.hour * 60 + t.minute


def _spans(band: tuple[datetime.time, datetime.time]) -> list[tuple[int, int]]:
    """Normalise a band to half-open minute ranges, splitting midnight wraps."""
    s, e = _minutes(band[0]), _minutes(band[1])
    if s == e:
        return [(0, 1440)]
    if s < e:
        return [(s, e)]
    return [(s, 1440), (0, e)]


def _overlaps(a: tuple[datetime.time, datetime.time], b: tuple[datetime.time, datetime.time]) -> bool:
    return any(s1 < e2 and s2 < e1 for s1, e1 in _spans(a) for s2, e2 in _spans(b))
