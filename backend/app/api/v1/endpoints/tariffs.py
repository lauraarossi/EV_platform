import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.tariff import ElectricityTariff, TariffRate
from app.schemas.tariff import RateQuoteRead, TariffCreate, TariffRead, TariffUpdate
from app.services import tariffs as tariff_svc

router = APIRouter(prefix="/tariffs", tags=["electricity tariffs"])


@router.get("/", response_model=list[TariffRead])
def list_tariffs(db: Session = Depends(get_db)):
    """Newest version first, so the current tariff is at the top."""
    return db.scalars(
        select(ElectricityTariff).order_by(ElectricityTariff.effective_from.desc())
    ).all()


@router.post("/", response_model=TariffRead, status_code=201)
def create_tariff(payload: TariffCreate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude={"rates"})
    tariff = ElectricityTariff(**data)
    tariff.rates = [TariffRate(**r.model_dump()) for r in payload.rates]

    db.add(tariff)
    # Adding a version starting today ends the one that was open before it.
    if payload.effective_to is None:
        tariff_svc.close_open_versions(db, payload.effective_from)

    db.commit()
    db.refresh(tariff)
    return tariff


@router.get("/current", response_model=TariffRead)
def current_tariff(on: datetime.date | None = None, db: Session = Depends(get_db)):
    tariff = tariff_svc.tariff_on(db, on or datetime.date.today())
    if not tariff:
        raise HTTPException(status_code=404, detail="No tariff in force on that date")
    return tariff


@router.get("/quote", response_model=RateQuoteRead)
def quote(
    date: datetime.date,
    at: datetime.time | None = None,
    db: Session = Depends(get_db),
):
    """The unit rate applying at a given moment — used to prefill charge cost."""
    found = tariff_svc.rate_for(db, date, at)
    if not found:
        raise HTTPException(
            status_code=404, detail="No tariff rate covers that date and time"
        )
    tariff, rate = found
    return RateQuoteRead(
        tariff_id=tariff.id,
        tariff_name=tariff.name,
        rate_name=rate.name,
        price_per_kwh=rate.price_per_kwh,
        exact=at is not None,
    )


@router.get("/{tariff_id}", response_model=TariffRead)
def get_tariff(tariff_id: int, db: Session = Depends(get_db)):
    tariff = db.get(ElectricityTariff, tariff_id)
    if not tariff:
        raise HTTPException(status_code=404, detail="Tariff not found")
    return tariff


@router.put("/{tariff_id}", response_model=TariffRead)
def update_tariff(tariff_id: int, payload: TariffUpdate, db: Session = Depends(get_db)):
    """Correct a version in place. To record a *rate change*, add a new version
    instead — editing rewrites history."""
    tariff = db.get(ElectricityTariff, tariff_id)
    if not tariff:
        raise HTTPException(status_code=404, detail="Tariff not found")

    for field, value in payload.model_dump(exclude={"rates"}).items():
        setattr(tariff, field, value)
    tariff.rates = [TariffRate(**r.model_dump()) for r in payload.rates]

    if payload.effective_to is None:
        tariff_svc.close_open_versions(db, payload.effective_from, exclude_id=tariff.id)

    db.commit()
    db.refresh(tariff)
    return tariff


@router.delete("/{tariff_id}", status_code=204)
def delete_tariff(tariff_id: int, db: Session = Depends(get_db)):
    tariff = db.get(ElectricityTariff, tariff_id)
    if not tariff:
        raise HTTPException(status_code=404, detail="Tariff not found")
    db.delete(tariff)
    db.commit()
