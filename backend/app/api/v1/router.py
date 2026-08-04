from fastapi import APIRouter
from app.api.v1.endpoints import health, vehicles, trips, charging

router = APIRouter(prefix="/api/v1")

router.include_router(health.router)
router.include_router(vehicles.router)
router.include_router(trips.router)
router.include_router(charging.router)
