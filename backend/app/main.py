import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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
    description="Track EV usage, charging costs, and compare against petrol equivalents",
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
        return FileResponse(index_file)
