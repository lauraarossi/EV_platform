from dataclasses import asdict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api.v1.endpoints.vehicles import owned_vehicle
from app.db.session import get_db
from app.models.charging_session import ChargingSession
from app.models.user import User
from app.models.vehicle import Vehicle
from app.security import get_current_user
from app.services import fuel_pricing, metrics

router = APIRouter(prefix="/stats", tags=["stats"])


def _load(db: Session, user: User, vehicle_id: int):
    vehicle = owned_vehicle(db, user, vehicle_id)
    sessions = (
        db.query(ChargingSession).filter(ChargingSession.vehicle_id == vehicle_id).all()
    )
    return vehicle, sessions


@router.get("/vehicles/{vehicle_id}/summary")
def vehicle_summary(
    vehicle_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    vehicle, sessions = _load(db, user, vehicle_id)
    return asdict(metrics.summarise(sessions, vehicle))


@router.get("/vehicles/{vehicle_id}/intervals")
def vehicle_intervals(
    vehicle_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    vehicle, sessions = _load(db, user, vehicle_id)
    intervals, anomalies = metrics.build_intervals(sessions, vehicle)
    return {"intervals": [asdict(i) for i in intervals], "anomalies": anomalies}


@router.get("/vehicles/{vehicle_id}/compare")
def compare_to_petrol(
    vehicle_id: int,
    comparison_vehicle_id: int,
    fallback_price_per_litre: float | None = Query(
        default=None,
        description="Used only for intervals with no stored price for that date",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Price the same driving as petrol, interval by interval.

    Each stretch of driving is costed at the pump price that applied *at the
    time*, not today's — pricing a year of history at this week's rate would be
    wrong in whichever direction fuel has moved.
    """
    vehicle, sessions = _load(db, user, vehicle_id)

    petrol = owned_vehicle(db, user, comparison_vehicle_id)
    if not petrol.fuel_consumption_l_per_100km:
        raise HTTPException(
            status_code=400,
            detail="Comparison vehicle needs a fuel consumption figure (L/100km)",
        )

    intervals, _ = metrics.build_intervals(sessions, vehicle)
    priced, petrol_total, used_fallback = fuel_pricing.price_intervals(
        db,
        intervals,
        l_per_100km=petrol.fuel_consumption_l_per_100km,
        fallback_price=fallback_price_per_litre,
    )

    # Only charges that close an interval are comparable: the first charge paid
    # for driving that predates the log, and has no distance to price against.
    ev_total = round(sum(i.cost or 0 for i in intervals), 2)
    distance = round(sum(i.distance_km for i in intervals), 2)
    unpriced = sum(1 for p in priced if p.petrol_cost is None)

    return {
        "distance_km": distance,
        "ev_cost": ev_total,
        "petrol_cost": petrol_total,
        "saving": round(petrol_total - ev_total, 2),
        "litres": round(sum(p.litres for p in priced), 2),
        "ev_cost_per_100km": round(ev_total / distance * 100, 2) if distance else None,
        "petrol_cost_per_100km": round(petrol_total / distance * 100, 2) if distance else None,
        "used_fallback_price": used_fallback,
        "unpriced_intervals": unpriced,
        "comparison_vehicle": f"{petrol.make} {petrol.model}",
        "l_per_100km": petrol.fuel_consumption_l_per_100km,
        "intervals": [asdict(p) for p in priced],
    }
