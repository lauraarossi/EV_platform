from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.charging_session import ChargingSession
from app.models.vehicle import Vehicle
from app.schemas.charging_session import (
    ChargingSessionCreate,
    ChargingSessionRead,
    ChargingSessionUpdate,
)

router = APIRouter(prefix="/charging", tags=["charging"])


def _require_vehicle(db: Session, vehicle_id: int) -> None:
    if not db.get(Vehicle, vehicle_id):
        raise HTTPException(status_code=404, detail="Vehicle not found")


@router.get("/", response_model=list[ChargingSessionRead])
def list_sessions(vehicle_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(ChargingSession)
    if vehicle_id:
        q = q.filter(ChargingSession.vehicle_id == vehicle_id)
    # Newest first for display; metrics re-sort chronologically themselves.
    return q.order_by(ChargingSession.date.desc(), ChargingSession.id.desc()).all()


@router.post("/", response_model=ChargingSessionRead, status_code=201)
def create_session(payload: ChargingSessionCreate, db: Session = Depends(get_db)):
    _require_vehicle(db, payload.vehicle_id)
    session = ChargingSession(**payload.model_dump())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/{session_id}", response_model=ChargingSessionRead)
def get_session(session_id: int, db: Session = Depends(get_db)):
    session = db.get(ChargingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Charging session not found")
    return session


@router.put("/{session_id}", response_model=ChargingSessionRead)
def update_session(
    session_id: int, payload: ChargingSessionUpdate, db: Session = Depends(get_db)
):
    session = db.get(ChargingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Charging session not found")
    _require_vehicle(db, payload.vehicle_id)
    for field, value in payload.model_dump().items():
        setattr(session, field, value)
    db.commit()
    db.refresh(session)
    return session


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: int, db: Session = Depends(get_db)):
    session = db.get(ChargingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Charging session not found")
    db.delete(session)
    db.commit()
