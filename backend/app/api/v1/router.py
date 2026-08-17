from fastapi import APIRouter, Depends

from app.api.v1.endpoints import (
    admin,
    auth,
    health,
    vehicles,
    fuel_events,
    stats,
    fuel_prices,
    tariffs,
    catalog,
)
from app.security import get_current_user

router = APIRouter(prefix="/api/v1")

# Open: the health probe, and the sign-in routes themselves.
router.include_router(health.router)
router.include_router(auth.router)

# Everything else requires an account. Vehicle, fuel-event, stats and tariff
# endpoints also scope their queries to the caller — this only gates the door.
router.include_router(vehicles.router)
router.include_router(fuel_events.router)
router.include_router(stats.router)
router.include_router(tariffs.router)

# Shared reference data: not owned by anyone, but this is not a public API, so
# it still needs a signed-in caller.
signed_in = [Depends(get_current_user)]
router.include_router(fuel_prices.router, dependencies=signed_in)
router.include_router(catalog.router, dependencies=signed_in)

# Admin only, enforced on the router itself rather than route by route. Every
# data refresh lives here, so there is no ungated path that skips the record
# kept of each run.
router.include_router(admin.router)
