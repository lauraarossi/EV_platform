from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.trip import Trip
from app.schemas.trip import TripCreate, TripRead, TripUpdate

router = APIRouter(prefix="/trips", tags=["trips"])


@router.get("/", response_model=list[TripRead])
def list_trips(vehicle_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(Trip)
    if vehicle_id:
        q = q.filter(Trip.vehicle_id == vehicle_id)
    return q.order_by(Trip.date.desc()).all()


@router.post("/", response_model=TripRead, status_code=201)
def create_trip(payload: TripCreate, db: Session = Depends(get_db)):
    trip = Trip(**payload.model_dump())
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


@router.get("/{trip_id}", response_model=TripRead)
def get_trip(trip_id: int, db: Session = Depends(get_db)):
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.put("/{trip_id}", response_model=TripRead)
def update_trip(trip_id: int, payload: TripUpdate, db: Session = Depends(get_db)):
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    for field, value in payload.model_dump().items():
        setattr(trip, field, value)
    db.commit()
    db.refresh(trip)
    return trip


@router.delete("/{trip_id}", status_code=204)
def delete_trip(trip_id: int, db: Session = Depends(get_db)):
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    db.delete(trip)
    db.commit()
