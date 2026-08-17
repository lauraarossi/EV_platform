"""The admin console's API.

Every route here requires the admin role, applied on the router so a new
endpoint cannot be added unprotected by forgetting a decorator.

Nothing here reads or writes another person's vehicles, charges or tariffs.
Admin covers the shared catalogue, the price feed and account roles; a car
someone logged stays theirs, and there is deliberately no route to it.
"""

from __future__ import annotations

import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.catalog import CatalogVehicle, CatalogSource
from app.models.fuel_event import FuelEvent
from app.models.fuel_price import FuelPrice
from app.models.import_run import ImportRun, ImportStatus
from app.models.tariff import ElectricityTariff
from app.models.user import User, UserRole
from app.models.vehicle import Vehicle
from app.schemas.admin import (
    AdminOverview,
    AdminUserRead,
    CatalogueSourceStat,
    ImportRunRead,
    RoleUpdate,
    TaskRead,
)
from app.security import get_current_admin
from app.services import admin_tasks

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_admin)],
)


@router.get("/overview", response_model=AdminOverview)
def overview(db: Session = Depends(get_db)):
    """Everything the console's front page shows, in one round trip."""
    by_source = [
        CatalogueSourceStat(
            source=source,
            entries=entries,
            with_trim=with_trim or 0,
            with_battery=with_battery or 0,
            with_consumption=with_consumption or 0,
        )
        for source, entries, with_trim, with_battery, with_consumption in db.execute(
            select(
                CatalogVehicle.source,
                func.count(),
                func.count(CatalogVehicle.trim),
                func.count(CatalogVehicle.battery_capacity_kwh),
                func.count(CatalogVehicle.fuel_consumption_l_per_100km),
            ).group_by(CatalogVehicle.source)
        )
    ]

    # Distinct *keys*, not names: the raw names triple-count a car the three
    # sources spell three ways, which is the whole reason the keys exist.
    makes = db.scalar(select(func.count(func.distinct(CatalogVehicle.make_key)))) or 0
    models = db.scalar(
        select(func.count()).select_from(
            select(CatalogVehicle.make_key, CatalogVehicle.model_key).distinct().subquery()
        )
    ) or 0

    latest: dict[str, ImportRunRead] = {}
    for key in admin_tasks.TASKS:
        run = db.scalars(
            select(ImportRun)
            .where(ImportRun.task == key)
            .order_by(ImportRun.started_at.desc())
            .limit(1)
        ).first()
        if run:
            latest[key] = ImportRunRead.model_validate(run)

    return AdminOverview(
        catalogue_total=sum(s.entries for s in by_source),
        catalogue_by_source=sorted(by_source, key=lambda s: s.entries, reverse=True),
        distinct_makes=makes,
        distinct_models=models,
        users=db.scalar(select(func.count()).select_from(User)) or 0,
        admins=db.scalar(
            select(func.count()).select_from(User).where(User.role == UserRole.admin)
        ) or 0,
        vehicles=db.scalar(select(func.count()).select_from(Vehicle)) or 0,
        fuel_events=db.scalar(select(func.count()).select_from(FuelEvent)) or 0,
        fuel_prices=db.scalar(select(func.count()).select_from(FuelPrice)) or 0,
        tariffs=db.scalar(select(func.count()).select_from(ElectricityTariff)) or 0,
        tasks=[
            TaskRead(
                key=t.key, label=t.label, description=t.description, slow=t.slow,
                last_run=latest.get(t.key),
            )
            for t in admin_tasks.TASKS.values()
        ],
    )


# --- refreshes ---------------------------------------------------------------

@router.post("/tasks/{task_key}/run", response_model=ImportRunRead, status_code=202)
def run_task(
    task_key: str,
    background: BackgroundTasks,
    params: dict | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Start a refresh and return immediately with its run record.

    202, not 200: the work has been accepted, not finished. Poll
    /admin/runs for the outcome.
    """
    if task_key not in admin_tasks.TASKS:
        raise HTTPException(status_code=404, detail=f"No such task: {task_key}")

    already = db.scalars(
        select(ImportRun).where(
            ImportRun.task == task_key, ImportRun.status == ImportStatus.running
        )
    ).first()
    if already:
        raise HTTPException(
            status_code=409, detail="That refresh is already running"
        )

    run = admin_tasks.start(db, task_key, admin)
    background.add_task(admin_tasks.execute, run.id, task_key, params or {})
    return ImportRunRead.model_validate(run)


@router.get("/runs", response_model=list[ImportRunRead])
def list_runs(
    task: str | None = None,
    limit: int = Query(default=25, le=200),
    db: Session = Depends(get_db),
):
    stmt = select(ImportRun).order_by(ImportRun.started_at.desc()).limit(limit)
    if task:
        stmt = stmt.where(ImportRun.task == task)
    return list(db.scalars(stmt))


# --- accounts ----------------------------------------------------------------

@router.get("/users", response_model=list[AdminUserRead])
def list_users(db: Session = Depends(get_db)):
    """Accounts and their roles — not their data, which stays private."""
    rows = db.execute(
        select(
            User,
            func.count(func.distinct(Vehicle.id)),
        )
        .outerjoin(Vehicle, Vehicle.user_id == User.id)
        .group_by(User.id)
        .order_by(User.created_at)
    ).all()
    return [
        AdminUserRead(
            id=u.id,
            email=u.email,
            display_name=u.display_name,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
            last_login_at=u.last_login_at,
            vehicles=vehicles,
        )
        for u, vehicles in rows
    ]


@router.patch("/users/{user_id}/role", response_model=AdminUserRead)
def set_role(
    user_id: int,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Grant or remove the admin role."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="No such account")

    # Stepping down is fine; being the last one out is not, as nobody could
    # then reach this endpoint to undo it.
    if user.id == admin.id and payload.role != UserRole.admin:
        remaining = db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.admin, User.id != user.id)
        )
        if not remaining:
            raise HTTPException(
                status_code=409,
                detail="You are the only admin — promote someone else first",
            )

    user.role = payload.role
    db.commit()
    db.refresh(user)

    vehicles = db.scalar(
        select(func.count()).select_from(Vehicle).where(Vehicle.user_id == user.id)
    ) or 0
    return AdminUserRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        vehicles=vehicles,
    )
