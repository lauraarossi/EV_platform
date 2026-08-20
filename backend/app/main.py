import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import router
from app.auth import BasicAuthMiddleware
from app.config import settings
from app.docs import router as docs_router

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Apply ADMIN_EMAILS to accounts that already exist.

    An account holding a valid session cookie never passes through sign-in, so
    without this it could wait out a thirty-day session before picking up the
    role. Failures here are logged rather than raised: not being able to
    promote someone is no reason to refuse to serve the app.
    """
    from app.db.session import SessionLocal
    from app.security import sync_admin_roles

    if settings.admin_email_list:
        try:
            with SessionLocal() as db:
                promoted = sync_admin_roles(db)
            if promoted:
                log.info("Granted the admin role to %d account(s)", promoted)
        except Exception:
            log.exception("Could not apply ADMIN_EMAILS at startup")
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Eevie API",
    description="Track what your car costs to run, and what another one would have",
    version="0.1.0",
    # Replaced by a themed version in app/docs.py that follows the app's
    # light/dark preference.
    docs_url=None,
)

# No-op unless APP_PASSWORD is set. Added before CORS so an unauthenticated
# request is refused without doing any further work.
app.add_middleware(BasicAuthMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Added last, so it wraps everything else and answers before any of it: a
# redirect should not depend on the shared password or on CORS.
@app.middleware("http")
async def redirect_www(request: Request, call_next):
    """Send www.example.com to example.com, keeping the path and query.

    One canonical hostname, so links, bookmarks and the session cookie all
    agree on where the app lives — a cookie set on the apex is not sent to the
    www host, and signing in on one would look like being signed out on the
    other.
    """
    host = request.headers.get("host", "").split(":")[0]
    if not host.startswith("www."):
        return await call_next(request)

    bare = host[4:]
    port = request.url.port
    netloc = bare if port in (None, 80, 443) else f"{bare}:{port}"
    return RedirectResponse(str(request.url.replace(netloc=netloc)), status_code=301)


# API routes are registered first so they always win over the SPA catch-all below.
app.include_router(docs_router)
app.include_router(router)


# ---------------------------------------------------------------------------
# Serve the built frontend from the same process.
#
# One service instead of two: no CORS, no API-base-URL to configure per
# environment, and half the hosting. The directory only exists in the
# production image (the Dockerfile builds the SPA and copies it here), so in
# local development this block is simply skipped and Vite serves the app.
# ---------------------------------------------------------------------------
STATIC_DIR = Path(__file__).resolve().parent / "static"

if STATIC_DIR.is_dir():
    assets = STATIC_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    index_file = STATIC_DIR / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        """Return real files when they exist, otherwise index.html.

        Client-side routes like /garage have no file behind them, so they must
        fall through to the app shell rather than 404. Path traversal is
        blocked by resolving and checking the result stays inside STATIC_DIR.
        """
        if full_path:
            candidate = (STATIC_DIR / full_path).resolve()
            if candidate.is_file() and candidate.is_relative_to(STATIC_DIR):
                return FileResponse(candidate)
        # Never cached. This file names which hashed bundles to load, so a
        # copy held by a browser points at assets a later deploy has removed —
        # a blank screen rather than an old version. The bundles themselves
        # carry a content hash and are safe to keep forever.
        return FileResponse(index_file, headers={"Cache-Control": "no-cache"})
