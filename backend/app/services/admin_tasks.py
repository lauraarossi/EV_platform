"""The data refreshes an admin can trigger, and the record of each attempt.

Every refresh goes through here rather than being called directly, so that all
of them are recorded the same way — a run that failed is far more interesting
than one that worked, and the catalogue looks identical either way, since the
previous rows are still sitting there.

They run in the background. The EEA import walks six years of registration data
over the network and a synchronous request would sit there long enough for a
proxy to give up on it, so the endpoint returns a run id and the console polls.
"""

from __future__ import annotations

import dataclasses
import datetime
import logging
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.import_run import ImportRun, ImportStatus
from app.models.user import User
from app.services import (
    catalog_naming,
    fx,
    eea_catalog,
    ev_catalog,
    merge_catalog,
    oil_bulletin,
    vca_catalog,
)

log = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class Task:
    key: str
    label: str
    description: str
    run: Callable[[Session, dict], Any]
    # Roughly how long it takes, so the console can warn before a long one.
    slow: bool = False


def _run_eea(db: Session, params: dict):
    years = params.get("years", "all")
    wanted = (
        sorted(eea_catalog.TABLES)
        if str(years).strip().lower() == "all"
        else [int(y) for y in str(years).split(",") if y.strip()]
    )
    return eea_catalog.ingest(
        db,
        country=str(params.get("country", "IE")).upper(),
        min_registrations=int(params.get("min_registrations", 3)),
        years=wanted,
    )


def _countries(params: dict) -> set[str] | None:
    """None means every country the bulletin covers."""
    raw = str(params.get("countries", "IE")).strip()
    if raw.lower() == "all":
        return None
    return {c.strip().upper() for c in raw.split(",") if c.strip()} or {"IE"}


TASKS: dict[str, Task] = {
    "evdb": Task(
        key="evdb",
        label="EV database",
        description="Battery, range and charging specs for electric cars.",
        run=lambda db, params: ev_catalog.ingest(db),
    ),
    "eea": Task(
        key="eea",
        label="EEA registrations",
        description=(
            "Every new car registered in Ireland, petrol and diesel included. "
            "The only source covering combustion engines."
        ),
        run=_run_eea,
        slow=True,
    ),
    "vca": Task(
        key="vca",
        label="VCA new-car data",
        description=(
            "Trim names and transmissions. Run uses the zip shipped with the "
            "app; upload a newer one to import it straight away — the rows "
            "persist, though the file itself is gone at the next deploy."
        ),
        # `data` is set when a zip is uploaded through the console; otherwise
        # the newest file committed under data/vca is used.
        run=lambda db, params: vca_catalog.ingest(
            db, data=params.get("data"), name=params.get("filename")
        ),
    ),
    "merge": Task(
        key="merge",
        label="Merge EV detail",
        description="Fill battery and range on electric EEA rows from evdb matches.",
        run=lambda db, params: merge_catalog.enrich_from_evdb(
            db, dry_run=bool(params.get("dry_run"))
        ),
    ),
    "rekey": Task(
        key="rekey",
        label="Regroup makes and models",
        description=(
            "Recompute the keys that fold three catalogues' spellings into one "
            "entry. Run after the naming rules change; imports nothing."
        ),
        run=lambda db, params: catalog_naming.rekey(db),
    ),
    "fx": Task(
        key="fx",
        label="Exchange rates",
        description=(
            "Daily euro reference rates from the ECB, so costs can be shown in "
            "pounds or dollars. Worth running daily; rates only move on "
            "working days."
        ),
        run=lambda db, params: fx.ingest(db),
    ),
    "oil-bulletin": Task(
        key="oil-bulletin",
        label="EU fuel prices",
        description="Weekly petrol and diesel prices from the EU Oil Bulletin.",
        run=lambda db, params: oil_bulletin.ingest(db, countries=_countries(params)),
    ),
}


# The order a full refresh runs in, and it is not arbitrary: merge fills EV
# detail on EEA rows from evdb, so both must be in first, and rekey regroups
# whatever ended up in the catalogue, so it goes last. Prices are independent
# and ride along at the end.
SEQUENCE = ["evdb", "eea", "vca", "merge", "rekey", "fx", "oil-bulletin"]


# Nothing here takes hours. A run still marked running after this did not
# finish — the process carrying it stopped, and nothing was left to write the
# ending. Without a sweep the row blocks that task forever.
STALE_AFTER = datetime.timedelta(hours=2)


def sweep_abandoned(db: Session) -> int:
    """Close out runs whose process is plainly gone.

    A background task lives in the web process. A deploy, a restart or a crash
    takes it with them, and the row it was writing stays `running` with nobody
    left to finish it — which then refuses every later attempt at that task as
    "already running". Recorded as failed rather than deleted: it did start,
    and something did stop it.
    """
    cutoff = _now() - STALE_AFTER
    stale = db.scalars(
        select(ImportRun).where(
            ImportRun.status == ImportStatus.running, ImportRun.started_at < cutoff
        )
    ).all()
    for run in stale:
        run.status = ImportStatus.failed
        run.error = (
            "Abandoned — still marked running after "
            f"{int(STALE_AFTER.total_seconds() // 3600)}h, so the process carrying "
            "it stopped without recording an ending."
        )
        run.finished_at = _now()
    if stale:
        db.commit()
    return len(stale)


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _as_dict(result: Any) -> dict | None:
    if result is None:
        return None
    if dataclasses.is_dataclass(result):
        result = dataclasses.asdict(result)
    if isinstance(result, dict):
        # Long lists (merge reports every unmatched name) would bloat the row.
        return {
            k: (v[:25] if isinstance(v, list) else v)
            for k, v in result.items()
        }
    return {"result": str(result)}


def start(db: Session, task_key: str, user: User | None) -> ImportRun:
    """Record a run as started and hand back its id."""
    run = ImportRun(
        task=task_key,
        status=ImportStatus.running,
        started_at=_now(),
        triggered_by_id=user.id if user else None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def run_sequence(
    task_keys: list[str] | None = None,
    params: dict | None = None,
    triggered_by_id: int | None = None,
    session_factory: Callable[[], Any] | None = None,
) -> None:
    """Run several refreshes back to back, each recorded separately.

    One run record per task rather than one for the batch: a full refresh that
    got three sources in and failed on the fourth is a useful thing to be able
    to read, and a single row saying "failed" would throw the other three away.

    A failure does not stop the rest. The sources are independent, and the two
    that are not — merge and rekey — are better run over whatever did arrive
    than skipped because something unrelated was down.
    """
    if session_factory is None:
        from app.db.session import SessionLocal

        session_factory = SessionLocal

    for key in task_keys or SEQUENCE:
        if key not in TASKS:
            log.warning("Skipping unknown refresh %r", key)
            continue
        with session_factory() as db:
            run = ImportRun(
                task=key,
                status=ImportStatus.running,
                started_at=_now(),
                triggered_by_id=triggered_by_id,
            )
            db.add(run)
            db.commit()
            run_id = run.id
        execute(run_id, key, params, session_factory=session_factory)


def execute(
    run_id: int,
    task_key: str,
    params: dict | None = None,
    session_factory: Callable[[], Any] | None = None,
) -> None:
    """Run the task and record how it went. Never raises: this runs detached
    from any request, so an exception would only be lost.

    It opens its own session, since the request's is closed by the time this
    runs. `session_factory` makes that explicit for tests — without it they
    would reach past their fixtures and work on the real database.
    """
    if session_factory is None:
        from app.db.session import SessionLocal

        session_factory = SessionLocal

    params = params or {}
    started = _now()

    with session_factory() as db:
        try:
            result = TASKS[task_key].run(db, params)
            status, payload, error = ImportStatus.ok, _as_dict(result), None
        except Exception as exc:  # noqa: BLE001 — recorded, then reported in the UI
            log.exception("Refresh %r failed", task_key)
            # The failed task may have left the session unusable.
            db.rollback()
            status, payload, error = ImportStatus.failed, None, f"{type(exc).__name__}: {exc}"

        run = db.get(ImportRun, run_id)
        if run is None:                     # deleted mid-run; nothing to update
            return
        run.status = status
        run.result = payload
        run.error = (error or "")[:500] or None
        run.finished_at = _now()
        run.duration_ms = int((run.finished_at - started).total_seconds() * 1000)
        db.commit()
