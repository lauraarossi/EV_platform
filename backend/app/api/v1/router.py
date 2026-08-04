from fastapi import APIRouter
from app.api.v1.endpoints import health, vehicles, charging, stats

router = APIRouter(prefix="/api/v1")

router.include_router(health.router)
router.include_router(vehicles.router)
router.include_router(charging.router)
router.include_router(stats.router)
