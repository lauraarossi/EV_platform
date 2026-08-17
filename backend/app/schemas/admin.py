import datetime

from pydantic import BaseModel

from app.models.catalog import CatalogSource
from app.models.import_run import ImportStatus
from app.models.user import UserRole


class ImportRunRead(BaseModel):
    id: int
    task: str
    status: ImportStatus
    started_at: datetime.datetime
    finished_at: datetime.datetime | None
    duration_ms: int | None
    result: dict | None
    error: str | None
    triggered_by_id: int | None

    model_config = {"from_attributes": True}


class TaskRead(BaseModel):
    key: str
    label: str
    description: str
    slow: bool
    last_run: ImportRunRead | None = None


class CatalogueSourceStat(BaseModel):
    source: CatalogSource
    entries: int
    # Coverage, so a source that imported plenty of rows carrying nothing
    # useful is visible as such.
    with_trim: int
    with_battery: int
    with_consumption: int


class AdminOverview(BaseModel):
    catalogue_total: int
    catalogue_by_source: list[CatalogueSourceStat]
    distinct_makes: int
    distinct_models: int

    users: int
    admins: int
    vehicles: int
    charging_sessions: int
    fuel_prices: int
    tariffs: int

    tasks: list[TaskRead]


class AdminUserRead(BaseModel):
    id: int
    email: str
    display_name: str | None
    role: UserRole
    is_active: bool
    created_at: datetime.datetime | None
    last_login_at: datetime.datetime | None
    # A count, not the vehicles themselves: the console has no business
    # showing what someone drives.
    vehicles: int

    model_config = {"from_attributes": True}


class RoleUpdate(BaseModel):
    role: UserRole
