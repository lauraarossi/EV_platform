"""The tools, without an account.

Everything here is stateless: a request carries the cars and the fill-ups, the
server does the arithmetic, and nothing is written down. That is what lets a
visitor use the app before deciding whether to keep anything — and it is also
the only page a search engine can reach, since the rest needs signing in.
"""

from __future__ import annotations

import datetime
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.fuel_price import FuelKind
from app.models.vehicle import FuelType
from app.schemas.public import CompareRequest, MetricsRequest
from app.services import comparison, fuel_pricing, metrics

router = APIRouter(prefix="/public", tags=["signed out"])

# What an Irish home pays off-peak, roughly. Only a starting point: it is shown
# in the form and can be changed, because someone on a night rate at 0.14 and
# someone on a standard rate at 0.35 cannot both be served by one number.
TYPICAL_PRICE_PER_KWH = 0.28


@router.get("/prices")
def suggested_prices(db: Session = Depends(get_db)):
    """Sensible starting figures for the form, and where each came from.

    Named as suggestions rather than presented as fact: a national weekly
    average is not what anyone actually paid, and the form says so.
    """
    today = datetime.date.today()
    petrol = fuel_pricing.price_on(db, today, fuel_kind=FuelKind.petrol_95)
    diesel = fuel_pricing.price_on(db, today, fuel_kind=FuelKind.diesel)

    return {
        "petrol": {
            "price_per_litre": petrol.price_per_litre if petrol else None,
            "as_of": petrol.as_of.isoformat() if petrol else None,
            "source": "EU Weekly Oil Bulletin, Irish national average",
        },
        "diesel": {
            "price_per_litre": diesel.price_per_litre if diesel else None,
            "as_of": diesel.as_of.isoformat() if diesel else None,
            "source": "EU Weekly Oil Bulletin, Irish national average",
        },
        "electricity": {
            "price_per_kwh": TYPICAL_PRICE_PER_KWH,
            "as_of": None,
            "source": "Typical Irish home rate — change it to yours",
        },
    }


@router.post("/metrics")
def metrics_for(payload: MetricsRequest):
    """Distance, consumption, cost and emissions for a log held in a browser."""
    vehicle = payload.vehicle.as_vehicle()
    events = [e.as_event(i + 1) for i, e in enumerate(payload.events)]

    intervals, anomalies = metrics.build_intervals(events, vehicle)
    return {
        "summary": asdict(metrics.summarise(events, vehicle)),
        "intervals": [asdict(i) for i in intervals],
        "anomalies": anomalies,
    }


@router.post("/compare")
def compare_two(payload: CompareRequest, db: Session = Depends(get_db)):
    """Price the same driving in two cars, for someone with no account.

    With a log, distance and what was actually paid both come from it. Without
    one, a distance is given and the rates in the form are used — there is no
    tariff and no receipt to do better with.
    """
    first = payload.first.as_vehicle(1)
    second = payload.second.as_vehicle(2)

    def quoted(vehicle) -> float | None:
        if vehicle.fuel_type == FuelType.electric:
            return payload.price_per_kwh
        return payload.price_per_litre

    if payload.distance_km is not None:
        intervals, measured = comparison.over_distance(payload.distance_km), None
    else:
        events = [e.as_event(i + 1) for i, e in enumerate(payload.events)]
        intervals, _ = metrics.build_intervals(events, first)
        if not intervals:
            raise HTTPException(
                status_code=422,
                detail="Those events give no distance — two readings apart are needed",
            )
        summary = metrics.summarise(events, first)
        measured = (
            summary.avg_efficiency_kwh_per_100km
            if first.fuel_type == FuelType.electric
            else summary.avg_consumption_l_per_100km
        )

    try:
        result = comparison.compare(
            db,
            # No account, so no tariff of anyone's to look up. The rates in the
            # form stand in for it.
            user_id=0,
            intervals=intervals,
            comparison_vehicle=second,
            driven_vehicle=first,
            measured_consumption=measured,
            measured_weight=payload.measured_weight,
            apply_gap_to_alternative=payload.apply_gap_to_alternative,
            driven_unit_price=quoted(first),
            alternative_unit_price=quoted(second),
            fallback_price_per_litre=payload.price_per_litre,
            fallback_price_per_kwh=payload.price_per_kwh,
        )
    except comparison.CannotCompare as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return asdict(result)
