from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.catalog import CatalogVehicle
from app.models.vehicle import FuelType
from app.schemas.catalog import CatalogMake, CatalogModel, CatalogVehicleRead
from app.services import eea_catalog, ev_catalog, irish_reg, merge_catalog

router = APIRouter(prefix="/catalog", tags=["vehicle catalogue"])


@router.get("/makes", response_model=list[CatalogMake])
def list_makes(fuel_type: FuelType | None = None, db: Session = Depends(get_db)):
    stmt = select(
        CatalogVehicle.make, func.count(func.distinct(CatalogVehicle.model))
    ).group_by(CatalogVehicle.make).order_by(CatalogVehicle.make)
    if fuel_type:
        stmt = stmt.where(CatalogVehicle.fuel_type == fuel_type)
    return [CatalogMake(make=m, model_count=n) for m, n in db.execute(stmt)]


@router.get("/models", response_model=list[CatalogModel])
def list_models(
    make: str = Query(..., description="Exact make from /catalog/makes"),
    fuel_type: FuelType | None = None,
    db: Session = Depends(get_db),
):
    stmt = (
        select(CatalogVehicle.make, CatalogVehicle.model, func.count())
        .where(CatalogVehicle.make == make)
        .group_by(CatalogVehicle.make, CatalogVehicle.model)
        .order_by(CatalogVehicle.model)
    )
    if fuel_type:
        stmt = stmt.where(CatalogVehicle.fuel_type == fuel_type)
    return [CatalogModel(make=mk, model=mo, variant_count=n) for mk, mo, n in db.execute(stmt)]


@router.get("/variants", response_model=list[CatalogVehicleRead])
def list_variants(
    make: str,
    model: str,
    db: Session = Depends(get_db),
):
    """Full specs per variant — the frontend prefills straight from these,
    so there is no second round trip after choosing one."""
    return db.scalars(
        select(CatalogVehicle)
        .where(CatalogVehicle.make == make, CatalogVehicle.model == model)
        # Commonly registered variants first, so the likely answer is near the top.
        .order_by(
            CatalogVehicle.registration_count.desc().nullslast(),
            CatalogVehicle.model_year.desc().nullslast(),
            CatalogVehicle.variant,
        )
    ).all()


@router.get("/search", response_model=list[CatalogVehicleRead])
def search(
    q: str = Query(..., min_length=2),
    limit: int = Query(default=25, le=100),
    db: Session = Depends(get_db),
):
    like = f"%{q.lower()}%"
    return db.scalars(
        select(CatalogVehicle)
        .where(
            func.lower(CatalogVehicle.make).like(like)
            | func.lower(CatalogVehicle.model).like(like)
            | func.lower(CatalogVehicle.variant).like(like)
        )
        .order_by(CatalogVehicle.make, CatalogVehicle.model, CatalogVehicle.variant)
        .limit(limit)
    ).all()


@router.get("/{catalog_id}", response_model=CatalogVehicleRead)
def get_entry(catalog_id: str, db: Session = Depends(get_db)):
    entry = db.get(CatalogVehicle, catalog_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Catalogue entry not found")
    return entry


@router.get("/years")
def available_years():
    """Which registration years can be imported."""
    return {"years": sorted(eea_catalog.TABLES), "latest": eea_catalog.LATEST_YEAR}


@router.get("/lookup/registration")
def lookup_registration(reg: str = Query(..., min_length=4, max_length=16)):
    """Decode an Irish plate. Year and county come from the plate itself; make
    and model are not derivable, as the national database is not public."""
    return asdict(irish_reg.decode(reg))


@router.post("/import/evdb")
def import_evdb(db: Session = Depends(get_db)):
    """Refresh from the open EV database. Safe to re-run: it updates catalogue
    rows in place and never touches the vehicles you own."""
    try:
        result = ev_catalog.ingest(db)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Import failed: {exc}") from exc
    return asdict(result)


@router.post("/import/eea")
def import_eea(
    country: str = Query(default="IE", min_length=2, max_length=2),
    min_registrations: int = Query(
        default=3, ge=1, description="Drop one-off variants below this many registrations"
    ),
    years: str = Query(
        default="all",
        description="Comma-separated registration years, or 'all' for every year available",
    ),
    db: Session = Depends(get_db),
):
    """Pull specs from the EEA CO2 monitoring dataset — the only free source
    covering petrol and diesel for European models.

    Importing several years is what turns up cars no longer sold new: an Audi
    A4, for instance, stopped appearing after 2023.
    """
    if years.strip().lower() == "all":
        wanted = sorted(eea_catalog.TABLES)
    else:
        try:
            wanted = [int(y) for y in years.split(",") if y.strip()]
        except ValueError:
            raise HTTPException(status_code=422, detail="years must be numbers or 'all'")

    try:
        result = eea_catalog.ingest(
            db, country=country.upper(), min_registrations=min_registrations, years=wanted
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Import failed: {exc}") from exc
    return asdict(result)


@router.post("/merge")
def merge(dry_run: bool = False, db: Session = Depends(get_db)):
    """Fill battery and range on electric EEA rows from matching evdb entries.
    Only empty fields are filled — nothing already known is overwritten."""
    return asdict(merge_catalog.enrich_from_evdb(db, dry_run=dry_run))
