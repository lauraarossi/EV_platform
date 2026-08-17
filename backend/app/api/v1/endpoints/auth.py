import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    AuthOptions,
    GoogleCallbackRequest,
    LoginRequest,
    RegisterRequest,
    UserRead,
)
from app.security import (
    apply_admin_policy,
    clear_session_cookie,
    get_current_user,
    hash_password,
    set_session_cookie,
    verify_google_id_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _as_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        has_password=user.password_hash is not None,
        has_google=user.google_sub is not None,
        is_admin=user.is_admin,
    )


def _find_by_email(db: Session, email: str) -> User | None:
    return db.scalars(
        select(User).where(func.lower(User.email) == email.strip().lower())
    ).first()


def _touch_login(db: Session, user: User) -> None:
    user.last_login_at = datetime.datetime.now(datetime.timezone.utc)
    # Sign-in is also when an account listed in ADMIN_EMAILS picks up the role,
    # so a deployment can grant it without anyone touching the database.
    apply_admin_policy(user)
    db.commit()


@router.get("/options", response_model=AuthOptions)
def options():
    """Lets the sign-in page hide what isn't configured, rather than showing a
    Google button that would fail."""
    return AuthOptions(
        google_enabled=bool(settings.google_client_id),
        registration_open=settings.allow_registration,
        google_client_id=settings.google_client_id or None,
    )


@router.post("/register", response_model=UserRead, status_code=201)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    if not settings.allow_registration:
        raise HTTPException(status_code=403, detail="Registration is closed")

    if _find_by_email(db, payload.email):
        raise HTTPException(status_code=409, detail="That email is already registered")

    try:
        hashed = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    user = User(
        email=payload.email.strip().lower(),
        display_name=payload.display_name,
        password_hash=hashed,
    )
    apply_admin_policy(user)
    db.add(user)
    db.commit()
    db.refresh(user)

    set_session_cookie(response, user)
    return _as_read(user)


@router.post("/login", response_model=UserRead)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = _find_by_email(db, payload.email)

    # Same message either way: saying "no such account" would let someone
    # enumerate which emails are registered.
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is disabled")

    _touch_login(db, user)
    set_session_cookie(response, user)
    return _as_read(user)


@router.post("/google", response_model=UserRead)
def google_sign_in(
    payload: GoogleCallbackRequest, response: Response, db: Session = Depends(get_db)
):
    """Verify the credential Google Identity Services handed the browser.

    Verification checks the signature, issuer, audience and expiry against
    Google's keys — so a forged token cannot get anyone in.
    """
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="Google sign-in isn't configured")

    try:
        claims = verify_google_id_token(payload.credential)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=f"Google sign-in failed: {exc}") from exc

    if not claims.get("email_verified"):
        raise HTTPException(
            status_code=401,
            detail="That Google account's email isn't verified",
        )

    sub = claims["sub"]
    email = claims["email"].strip().lower()

    user = db.scalars(select(User).where(User.google_sub == sub)).first()

    if user is None:
        # Link to an existing password account rather than creating a second
        # one for the same person. Safe because Google says the email is
        # verified, and the address is unique in our table.
        user = _find_by_email(db, email)
        if user is not None:
            user.google_sub = sub
        else:
            if not settings.allow_registration:
                raise HTTPException(status_code=403, detail="Registration is closed")
            user = User(email=email, google_sub=sub)
            db.add(user)

    # Refresh the profile bits Google owns.
    user.display_name = user.display_name or claims.get("name")
    user.avatar_url = claims.get("picture") or user.avatar_url
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is disabled")

    db.commit()
    db.refresh(user)

    _touch_login(db, user)
    set_session_cookie(response, user)
    return _as_read(user)


@router.post("/logout", status_code=204)
def logout(response: Response):
    clear_session_cookie(response)


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)):
    return _as_read(user)
