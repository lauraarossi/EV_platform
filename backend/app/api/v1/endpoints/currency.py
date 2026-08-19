"""Currency: what the client formats money in, and what to convert with."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.security import get_current_user
from app.services import fx

router = APIRouter(prefix="/currency", tags=["currency"])


class CurrencyChoice(BaseModel):
    code: str
    symbol: str


class Rates(BaseModel):
    base: str
    # Newest rate held per currency. The client converts with these for
    # display; anything costed against a date is converted on the server, where
    # the whole series is.
    rates: dict[str, float]
    choices: list[CurrencyChoice]
    source: str


class CurrencyUpdate(BaseModel):
    currency: str

    @field_validator("currency")
    @classmethod
    def known(cls, v: str) -> str:
        code = v.strip().upper()
        if code not in fx.CURRENCIES:
            raise ValueError(f"Unsupported currency: {v}")
        return code


@router.get("/", response_model=Rates)
def rates(db: Session = Depends(get_db)):
    """Everything the client needs to show money in another currency."""
    return Rates(
        base=fx.BASE,
        rates=fx.latest_rates(db),
        choices=[CurrencyChoice(code=c, symbol=s) for c, s in fx.CURRENCIES.items()],
        source=fx.SOURCE,
    )


@router.put("/", response_model=CurrencyUpdate)
def set_currency(
    payload: CurrencyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Kept on the account rather than in the browser, unlike the unit system:
    it decides how the money someone entered is read back, so it should follow
    them to a different device rather than reset to euro."""
    if payload.currency != fx.BASE and not fx.rate_on(db, payload.currency):
        raise HTTPException(
            status_code=409,
            detail=f"No exchange rate for {payload.currency} yet — refresh rates first",
        )
    user.currency = payload.currency
    db.commit()
    return payload
