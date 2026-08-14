from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.endpoints.vehicles import owned_vehicle
from app.db.session import get_db
from app.models.charging_session import ChargingSession
from app.models.user import User
from app.models.vehicle import Vehicle
from app.schemas.charging_session import (
    ChargingSessionCreate,
    ChargingSessionRead,
    ChargingSessionUpdate,
)
from app.security import get_current_user

router = APIRouter(prefix="/charging", tags=["charging"])


def owned_session(db: Session, user: User, session_id: int) -> ChargingSession:
    """A charge is owned through its vehicle, so the join does the checking."""
    session = db.scalars(
        select(ChargingSession)
        .join(Vehicle, Vehicle.id == ChargingSession.vehicle_id)
        .where(ChargingSession.id == session_id, Vehicle.user_id == user.id)
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Charging session not found")
    return session


@router.get("/", response_model=list[ChargingSessionRead])
def list_sessions(
    vehicle_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(ChargingSession)
        .join(Vehicle, Vehicle.id == ChargingSession.vehicle_id)
        .where(Vehicle.user_id == user.id)
    )
    if vehicle_id:
        stmt = stmt.where(ChargingSession.vehicle_id == vehicle_id)
    # Newest first for display; metrics re-sort chronologically themselves.
    return db.scalars(
        stmt.order_by(ChargingSession.date.desc(), ChargingSession.id.desc())
    ).all()


@router.post("/", response_model=ChargingSessionRead, status_code=201)
def create_session(
    payload: ChargingSessionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    owned_vehicle(db, user, payload.vehicle_id)  # 404s if it isn't yours
    session = ChargingSession(**payload.model_dump())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/{session_id}", response_model=ChargingSessionRead)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return owned_session(db, user, session_id)


@router.put("/{session_id}", response_model=ChargingSessionRead)
def update_session(
    session_id: int,
    payload: ChargingSessionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = owned_session(db, user, session_id)
    # Re-checked so a charge can't be moved onto someone else's vehicle.
    owned_vehicle(db, user, payload.vehicle_id)
    for field, value in payload.model_dump().items():
        setattr(session, field, value)
    db.commit()
    db.refresh(session)
    return session


@router.delete("/{session_id}", status_code=204)
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    db.delete(owned_session(db, user, session_id))
    db.commit()
