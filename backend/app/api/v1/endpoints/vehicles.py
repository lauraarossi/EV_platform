from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.vehicle import Vehicle
from app.schemas.vehicle import VehicleCreate, VehicleRead, VehicleUpdate
from app.security import get_current_user

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


def owned_vehicle(db: Session, user: User, vehicle_id: int) -> Vehicle:
    """Fetch a vehicle belonging to this user.

    Someone else's vehicle reports 404 rather than 403: a 403 would confirm
    the record exists, which is itself a small leak.
    """
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.user_id != user.id:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


@router.get("/", response_model=list[VehicleRead])
def list_vehicles(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(
        select(Vehicle).where(Vehicle.user_id == user.id).order_by(Vehicle.id)
    ).all()


@router.post("/", response_model=VehicleRead, status_code=201)
def create_vehicle(
    payload: VehicleCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    vehicle = Vehicle(**payload.model_dump(), user_id=user.id)
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.get("/{vehicle_id}", response_model=VehicleRead)
def get_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return owned_vehicle(db, user, vehicle_id)


@router.put("/{vehicle_id}", response_model=VehicleRead)
def update_vehicle(
    vehicle_id: int,
    payload: VehicleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    vehicle = owned_vehicle(db, user, vehicle_id)
    for field, value in payload.model_dump().items():
        setattr(vehicle, field, value)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.delete("/{vehicle_id}", status_code=204)
def delete_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    db.delete(owned_vehicle(db, user, vehicle_id))
    db.commit()
