"""Passwords, sessions, and identifying the caller.

Sessions are a signed JWT in an httpOnly cookie rather than a token held in
JavaScript: the frontend is served from the same origin as the API, so the
browser attaches the cookie by itself, and script on the page cannot read it
even if something manages to inject one. Nothing to store, nothing to refresh,
and it works the same on a phone.
"""

from __future__ import annotations

import datetime

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.user import User

ALGORITHM = "HS256"

# Google publishes the public keys its ID tokens are signed with here. PyJWKClient
# fetches and caches them, so verification needs no extra dependency — the
# official google-auth library pulls in `requests`, which we otherwise don't use.
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")

_jwks_client: jwt.PyJWKClient | None = None
# bcrypt silently truncates at 72 bytes, so refuse longer input rather than
# accepting a password whose tail is ignored.
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LENGTH = 8


# --- passwords --------------------------------------------------------------

def hash_password(password: str) -> str:
    _check_length(password)
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def _check_length(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password.encode()) > MAX_PASSWORD_BYTES:
        raise ValueError("Password is too long (max 72 bytes)")


# --- sessions ---------------------------------------------------------------

def create_session_token(user: User) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": str(user.id),
        "iat": now,
        "exp": now + datetime.timedelta(days=settings.session_days),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def read_session_token(token: str) -> int | None:
    """Return the user id in a valid token, or None if it is bad or expired."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        return None


def set_session_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=create_session_token(user),
        max_age=settings.session_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        # Lax still sends the cookie on a top-level redirect back from Google.
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


# --- Google ID tokens -------------------------------------------------------

def verify_google_id_token(credential: str) -> dict:
    """Check a Google ID token and return its claims.

    Verifies the signature against Google's published keys, and that the token
    was issued by Google *for this application* — without the audience check a
    token minted for any other site would be accepted here.

    Raises ValueError if anything is wrong.
    """
    global _jwks_client

    if not settings.google_client_id:
        raise ValueError("Google sign-in isn't configured")

    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(GOOGLE_JWKS_URL, cache_keys=True)

    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(credential)
        claims = jwt.decode(
            credential,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise ValueError(str(exc)) from exc

    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise ValueError("Token wasn't issued by Google")

    if not claims.get("email"):
        raise ValueError("Google didn't return an email address")

    return claims


# --- dependencies -----------------------------------------------------------

def get_current_user_optional(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None

    user_id = read_session_token(token)
    if user_id is None:
        return None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(
    user: User | None = Depends(get_current_user_optional),
) -> User:
    """Require a signed-in account. Everything owning data depends on this."""
    if user is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    return user
