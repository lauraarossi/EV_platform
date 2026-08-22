"""Taking feedback from anyone, signed in or not."""

from __future__ import annotations

import datetime
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.feedback import Feedback
from app.models.user import User
from app.security import get_current_user_optional

router = APIRouter(prefix="/feedback", tags=["feedback"])

MAX_MESSAGE = 4000
# Enough for anyone with something to say, few enough that a script gets bored.
MAX_PER_HOUR = 5

# Per-address counters, in memory. Deliberately not in the database: this is
# throttling, not a record, and losing it on restart costs nothing. One process
# serves the whole app, so there is nothing to share it with.
_recent: dict[str, list[float]] = {}


def _rate_limited(ip: str, now: float | None = None) -> bool:
    now = now or time.time()
    hits = [t for t in _recent.get(ip, []) if now - t < 3600]
    _recent[ip] = hits + [now]
    return len(hits) >= MAX_PER_HOUR


class FeedbackCreate(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE)
    page: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    # A field no person sees and every naive bot fills in. Named plausibly,
    # since "honeypot" in the markup rather defeats it.
    website: str | None = None


@router.post("/", status_code=201)
def leave_feedback(
    payload: FeedbackCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Open on purpose. A visitor deciding whether to bother signing up has the
    feedback most worth hearing, and asking them to make an account first is
    how you never hear it."""
    if payload.website:
        # Silently accepted. Telling a bot it was spotted only teaches it.
        return {"status": "received"}

    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Nothing to send")

    client = request.client.host if request.client else "unknown"
    if _rate_limited(client):
        raise HTTPException(
            status_code=429, detail="That is a lot of feedback at once — try again later"
        )

    db.add(
        Feedback(
            message=message[:MAX_MESSAGE],
            page=payload.page,
            user_agent=(request.headers.get("user-agent") or "")[:400] or None,
            user_id=user.id if user else None,
            email=(payload.email or (user.email if user else None)),
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
    )
    db.commit()
    return {"status": "received"}
