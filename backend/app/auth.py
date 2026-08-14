"""Optional HTTP basic auth for the whole app.

Eevie has no user accounts — it is a single-person tool. But a public URL with
no protection at all means anyone who finds it can read the data and delete
records, so this puts one password in front of everything.

It is opt-in: with `APP_PASSWORD` unset the middleware waves every request
through, which keeps local development exactly as it was. Set the variable in
the deployed environment and the app asks for a password once, then the browser
remembers it — which works fine on a phone.

The health endpoint is always exempt, or the platform's health check would fail
and the deploy would be marked unhealthy and restarted forever.
"""

from __future__ import annotations

import base64
import binascii
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings

# Kept open so uptime checks and the platform health probe still work.
EXEMPT_PATHS = frozenset({"/api/v1/health"})

CHALLENGE = {"WWW-Authenticate": 'Basic realm="Eevie", charset="UTF-8"'}


def _credentials_match(header: str) -> bool:
    scheme, _, encoded = header.partition(" ")
    if scheme.lower() != "basic" or not encoded:
        return False

    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False

    username, _, password = decoded.partition(":")

    # compare_digest on both parts, and always both, so a wrong username takes
    # the same time as a wrong password.
    user_ok = secrets.compare_digest(username, settings.app_username)
    pass_ok = secrets.compare_digest(password, settings.app_password)
    return user_ok and pass_ok


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.app_password:
            return await call_next(request)

        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        header = request.headers.get("authorization", "")
        if not _credentials_match(header):
            return Response(status_code=401, headers=CHALLENGE)

        return await call_next(request)
