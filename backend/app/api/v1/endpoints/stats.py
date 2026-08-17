from dataclasses import asdict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api.v1.endpoints.vehicles import owned_vehicle
from app.db.session import get_db
from app.models.fuel_event import FuelEvent
from app.models.user import User
from app.security import get_current_user
from app.services import comparison, metrics

router = APIRouter(prefix="/stats", tags=["stats"])


def _load(db: Session, user: User, vehicle_id: int):
    vehicle = owned_vehicle(db, user, vehicle_id)
    events = db.query(FuelEvent).filter(FuelEvent.vehicle_id == vehicle_id).all()
    return vehicle, events


@router.get("/vehicles/{vehicle_id}/summary")
def vehicle_summary(
    vehicle_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    vehicle, events = _load(db, user, vehicle_id)
    return asdict(metrics.summarise(events, vehicle))


@router.get("/vehicles/{vehicle_id}/intervals")
def vehicle_intervals(
    vehicle_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    vehicle, events = _load(db, user, vehicle_id)
    intervals, anomalies = metrics.build_intervals(events, vehicle)
    return {"intervals": [asdict(i) for i in intervals], "anomalies": anomalies}


@router.get("/vehicles/{vehicle_id}/compare")
def compare_vehicles(
    vehicle_id: int,
    comparison_vehicle_id: int,
    fallback_price_per_litre: float | None = Query(
        default=None,
        description="Used only for intervals with no stored pump price for that date",
    ),
    fallback_price_per_kwh: float | None = Query(
        default=None,
        description="Used only when no electricity tariff covers that date",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Price the driving you actually did as though another car had done it.

    Works in either direction — an EV against petrol, or a diesel against an EV
    — and costs each stretch at the rate that applied at the time rather than
    today's, which would misstate any history longer than a few weeks.
    """
    vehicle, events = _load(db, user, vehicle_id)
    alternative = owned_vehicle(db, user, comparison_vehicle_id)

    intervals, _ = metrics.build_intervals(events, vehicle)
    try:
        result = comparison.compare(
            db,
            user.id,
            intervals,
            alternative,
            fallback_price_per_litre=fallback_price_per_litre,
            fallback_price_per_kwh=fallback_price_per_kwh,
        )
    except comparison.CannotCompare as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return asdict(result) | {"vehicle": f"{vehicle.make} {vehicle.model}"}
