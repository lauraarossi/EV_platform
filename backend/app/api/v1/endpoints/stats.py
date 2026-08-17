from dataclasses import asdict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api.v1.endpoints.vehicles import owned_vehicle
from app.db.session import get_db
from app.models.fuel_event import FuelEvent
from app.models.user import User
from app.models.vehicle import FuelType
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
    distance_km: float | None = Query(
        default=None, gt=0,
        description=(
            "Compare over this distance instead of the logged history. Required "
            "when the first car has nothing logged — two Showroom cars have no "
            "history between them, and how far is then the only missing piece."
        ),
    ),
    fallback_price_per_litre: float | None = Query(
        default=None,
        description="Used only for intervals with no stored pump price for that date",
    ),
    fallback_price_per_kwh: float | None = Query(
        default=None,
        description="Used only when no electricity tariff covers that date",
    ),
    apply_gap_to_alternative: bool = Query(
        default=False,
        description=(
            "Lift the second car's figure by the same proportion the first is "
            "being lifted above its own brochure figure, so the two stay "
            "comparable while both describe real driving."
        ),
    ),
    measured_weight: float = Query(
        default=0.0, ge=0, le=1,
        description=(
            "How far your car's consumption slides from the figure you entered "
            "(0) towards the one your log actually shows (1). 0 keeps both cars "
            "strictly like-for-like."
        ),
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Price the same driving in two cars.

    Either car can be anything you have recorded — two from the Garage, two
    from the Showroom, or one of each. With a log behind the first car each
    stretch is costed at the rate that applied at the time; without one, give a
    distance and it is costed at today's.
    """
    vehicle, events = _load(db, user, vehicle_id)
    # The same car on both sides is allowed, and useful: with the slider moved
    # it weighs what the car actually achieves against what it is quoted at.
    alternative = owned_vehicle(db, user, comparison_vehicle_id)

    logged, _ = metrics.build_intervals(events, vehicle)

    if distance_km is not None:
        intervals, measured = comparison.over_distance(distance_km), None
    elif logged:
        intervals = logged
        # Offered as the other end of the slider, and reported either way so
        # the page can show what the entered figure is being weighed against.
        summary = metrics.summarise(events, vehicle)
        measured = (
            summary.avg_efficiency_kwh_per_100km
            if vehicle.fuel_type == FuelType.electric
            else summary.avg_consumption_l_per_100km
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{vehicle.make} {vehicle.model} has nothing logged, so there is no "
                "distance to compare over — pass distance_km"
            ),
        )

    try:
        result = comparison.compare(
            db,
            user.id,
            intervals,
            alternative,
            driven_vehicle=vehicle,
            measured_consumption=measured,
            measured_weight=measured_weight,
            apply_gap_to_alternative=apply_gap_to_alternative,
            fallback_price_per_litre=fallback_price_per_litre,
            fallback_price_per_kwh=fallback_price_per_kwh,
        )
    except comparison.CannotCompare as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return asdict(result) | {"vehicle": f"{vehicle.make} {vehicle.model}"}
