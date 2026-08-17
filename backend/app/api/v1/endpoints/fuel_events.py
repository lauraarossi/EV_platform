from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.endpoints.vehicles import owned_vehicle
from app.db.session import get_db
from app.models.fuel_event import FuelEvent
from app.models.user import User
from app.models.vehicle import Vehicle
from app.schemas.fuel_event import FuelEventCreate, FuelEventRead, FuelEventUpdate
from app.security import get_current_user

router = APIRouter(prefix="/fuel-events", tags=["fuel events"])


def owned_event(db: Session, user: User, event_id: int) -> FuelEvent:
    """An event is owned through its vehicle, so the join does the checking."""
    event = db.scalars(
        select(FuelEvent)
        .join(Vehicle, Vehicle.id == FuelEvent.vehicle_id)
        .where(FuelEvent.id == event_id, Vehicle.user_id == user.id)
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Fuel event not found")
    return event


@router.get("/", response_model=list[FuelEventRead])
def list_events(
    vehicle_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(FuelEvent)
        .join(Vehicle, Vehicle.id == FuelEvent.vehicle_id)
        .where(Vehicle.user_id == user.id)
    )
    if vehicle_id:
        stmt = stmt.where(FuelEvent.vehicle_id == vehicle_id)
    # Newest first for display; metrics re-sort chronologically themselves.
    return db.scalars(stmt.order_by(FuelEvent.date.desc(), FuelEvent.id.desc())).all()


@router.post("/", response_model=FuelEventRead, status_code=201)
def create_event(
    payload: FuelEventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    owned_vehicle(db, user, payload.vehicle_id)  # 404s if it isn't yours
    event = FuelEvent(**payload.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/{event_id}", response_model=FuelEventRead)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return owned_event(db, user, event_id)


@router.put("/{event_id}", response_model=FuelEventRead)
def update_event(
    event_id: int,
    payload: FuelEventUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    event = owned_event(db, user, event_id)
    # Re-checked so an event can't be moved onto someone else's vehicle.
    owned_vehicle(db, user, payload.vehicle_id)
    for field, value in payload.model_dump().items():
        setattr(event, field, value)
    db.commit()
    db.refresh(event)
    return event


@router.delete("/{event_id}", status_code=204)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    db.delete(owned_event(db, user, event_id))
    db.commit()
