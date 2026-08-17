import datetime
import enum

from sqlalchemy import String, DateTime, Integer, Enum, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ImportStatus(str, enum.Enum):
    running = "running"
    ok = "ok"
    failed = "failed"


class ImportRun(Base):
    """One attempt at refreshing a data source.

    Recorded so the admin console can answer "when was this last refreshed, and
    did it work" from fact rather than inference. Failures are kept, not
    discarded: a source that has been quietly failing for a month is exactly
    what this is meant to surface — the catalogue looks fine either way, since
    the previous rows are still sitting there.
    """

    __tablename__ = "import_runs"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Which refresh this was: an import source name, or "merge"/"rekey".
    task: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[ImportStatus] = mapped_column(Enum(ImportStatus), index=True)

    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    # The importer's own result, whatever shape it takes — row counts differ by
    # source and pinning them to columns would mean a migration per source.
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String(500))

    # Kept if the account is later deleted: the record is about the data, not
    # the person, and losing the history would be worse than a null.
    triggered_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
