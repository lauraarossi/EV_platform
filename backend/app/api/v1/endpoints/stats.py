from dataclasses import asdict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.charging_session import ChargingSession
from app.models.vehicle import Vehicle
from app.services import metrics

router = APIRouter(prefix="/stats", tags=["stats"])


def _load(db: Session, vehicle_id: int):
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    sessions = (
        db.query(ChargingSession).filter(ChargingSession.vehicle_id == vehicle_id).all()
    )
    return vehicle, sessions


@router.get("/vehicles/{vehicle_id}/summary")
def vehicle_summary(vehicle_id: int, db: Session = Depends(get_db)):
    vehicle, sessions = _load(db, vehicle_id)
    return asdict(metrics.summarise(sessions, vehicle))


@router.get("/vehicles/{vehicle_id}/intervals")
def vehicle_intervals(vehicle_id: int, db: Session = Depends(get_db)):
    vehicle, sessions = _load(db, vehicle_id)
    intervals, anomalies = metrics.build_intervals(sessions, vehicle)
    return {"intervals": [asdict(i) for i in intervals], "anomalies": anomalies}
