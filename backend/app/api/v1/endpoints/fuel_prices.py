import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.fuel_price import FuelPrice, FuelKind, PriceSource
from app.schemas.fuel_price import FuelPriceCreate, FuelPriceRead, PriceQuoteRead
from app.services import fuel_pricing

router = APIRouter(prefix="/fuel-prices", tags=["fuel prices"])


@router.get("/", response_model=list[FuelPriceRead])
def list_prices(
    country: str = "IE",
    region: str | None = None,
    fuel_kind: FuelKind = FuelKind.petrol_95,
    source: PriceSource | None = None,
    since: datetime.date | None = None,
    limit: int = Query(default=200, le=2000),
    db: Session = Depends(get_db),
):
    stmt = select(FuelPrice).where(
        FuelPrice.country == country, FuelPrice.fuel_kind == fuel_kind
    )
    if region is not None:
        stmt = stmt.where(FuelPrice.region == region)
    if source is not None:
        stmt = stmt.where(FuelPrice.source == source)
    if since is not None:
        stmt = stmt.where(FuelPrice.date >= since)
    return db.scalars(stmt.order_by(FuelPrice.date.desc()).limit(limit)).all()


@router.post("/", response_model=FuelPriceRead, status_code=201)
def upsert_manual_price(payload: FuelPriceCreate, db: Session = Depends(get_db)):
    """Record your own price. Overwrites a previous manual entry for the same
    date/place/fuel rather than creating a duplicate."""
    existing = db.scalars(
        select(FuelPrice).where(
            FuelPrice.date == payload.date,
            FuelPrice.country == payload.country,
            FuelPrice.region == payload.region,
            FuelPrice.fuel_kind == payload.fuel_kind,
            FuelPrice.source == PriceSource.manual,
        )
    ).first()

    if existing:
        existing.price_per_litre = payload.price_per_litre
        existing.currency = payload.currency
        db.commit()
        db.refresh(existing)
        return existing

    price = FuelPrice(**payload.model_dump(), source=PriceSource.manual)
    db.add(price)
    db.commit()
    db.refresh(price)
    return price


@router.delete("/{price_id}", status_code=204)
def delete_price(price_id: int, db: Session = Depends(get_db)):
    price = db.get(FuelPrice, price_id)
    if not price:
        raise HTTPException(status_code=404, detail="Price not found")
    if price.source != PriceSource.manual:
        raise HTTPException(
            status_code=400,
            detail="Only manually entered prices can be deleted; re-ingest to refresh feed data",
        )
    db.delete(price)
    db.commit()


@router.get("/quote", response_model=PriceQuoteRead)
def quote(
    date: datetime.date,
    country: str = "IE",
    region: str = "",
    fuel_kind: FuelKind = FuelKind.petrol_95,
    db: Session = Depends(get_db),
):
    """Which price applies on a given date — what the comparison actually uses."""
    q = fuel_pricing.price_on(db, date, country=country, region=region, fuel_kind=fuel_kind)
    if not q:
        raise HTTPException(
            status_code=404,
            detail="No price available for that date. Import the Oil Bulletin or add one manually.",
        )
    return q
