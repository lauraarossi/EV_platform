"""The database engine, built to survive a database that sleeps.

Railway's serverless Postgres stops when idle and boots on the first
connection, which takes a few seconds. Two things follow, and neither is
hypothetical — both have taken the app down:

  * a connection held in the pool is dead once the server has stopped, so the
    next request to reuse it fails;
  * a fresh connection during the boot is refused outright, with
    "the database system is starting up".

Left alone, both surface as a 500 on whatever request happened to be first —
which is why signing in failed once and then worked immediately after.
"""

from __future__ import annotations

import logging
import time

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.config import settings

log = logging.getLogger(__name__)

# Short and few: this covers a wake, not an outage. A request cannot sit for
# minutes waiting, so if the database is genuinely gone we fail fast and let
# the error be the honest one.
CONNECT_ATTEMPTS = 5
CONNECT_BACKOFF = 1.5

# Postgres says this while booting. Anything else is a real failure and is
# raised immediately rather than retried.
WAKING = ("starting up", "starting-up", "not yet accepting", "recovery mode")

engine = create_engine(
    settings.database_url,
    # Checks a pooled connection is alive before handing it over, and quietly
    # replaces it if not. Without this every sleep leaves the pool full of
    # connections that fail on first use.
    pool_pre_ping=True,
    # Nothing should sit in the pool across a long idle period anyway.
    pool_recycle=1800,
)


@event.listens_for(engine, "do_connect")
def _retry_while_waking(dialect, conn_rec, cargs, cparams):
    """Retry a connection refused because the server is still booting.

    Returning a DBAPI connection here replaces the one SQLAlchemy would have
    made; returning None lets it proceed normally.
    """
    last: Exception | None = None
    for attempt in range(1, CONNECT_ATTEMPTS + 1):
        try:
            return dialect.dbapi.connect(*cargs, **cparams)
        except Exception as exc:  # noqa: BLE001 — re-raised below if not a wake
            if not any(hint in str(exc).lower() for hint in WAKING):
                raise
            last = exc
            if attempt < CONNECT_ATTEMPTS:
                log.info("Database is waking; retrying (%d/%d)", attempt, CONNECT_ATTEMPTS)
                time.sleep(CONNECT_BACKOFF * attempt)

    assert last is not None
    raise last


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
