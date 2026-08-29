"""Commands meant to be run by something other than a person.

Railway's scheduler starts a one-off container and runs a command in it, which
is where this is aimed. Doing it that way rather than with a timer inside the
web process is deliberate: that process is restarted on every deploy and can be
replaced at any moment, so a thread sleeping until Tuesday is a schedule that
quietly stops existing. A scheduler outside the app has no such problem.

    python -m app.cli refresh                 # everything, in dependency order
    python -m app.cli refresh --only fx       # just one
    python -m app.cli refresh --list          # what there is to run
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from sqlalchemy import text

from app.services import admin_tasks

log = logging.getLogger(__name__)

# Long enough for a sleeping database to wake. Railway's serverless Postgres
# stops when idle and boots on the first connection, which is exactly the state
# a job scheduled for 3am finds it in — nothing has touched it for hours. Short
# enough that a genuinely unreachable one fails the run rather than leaving the
# container up, which would make Railway skip the next scheduled fire.
DB_WAIT_SECONDS = 180


def wait_for_database(timeout: int | None = None) -> bool:
    """Block until the database answers, or give up.

    A scheduled container and the database it needs start independently, and
    Postgres refuses connections with "the database system is starting up"
    for the first few seconds after it wakes. Without this the job simply
    crashes at 3am, every night, for a condition that clears itself in ten
    seconds.
    """
    from app.db.session import SessionLocal

    # Resolved here rather than as a default argument, which would bind the
    # value at import and ignore anything that changed it since.
    timeout = DB_WAIT_SECONDS if timeout is None else timeout
    deadline = time.monotonic() + timeout
    attempt = 0
    while True:
        attempt += 1
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
            if attempt > 1:
                log.info("Database ready after %d attempts", attempt)
            return True
        except Exception as exc:
            if time.monotonic() >= deadline:
                log.error("Database still unreachable after %ds: %s", timeout, exc)
                return False
            # Backing off rather than hammering: it is booting, not broken.
            time.sleep(min(2 * attempt, 10))


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    refresh = sub.add_parser("refresh", help="Re-import the reference data")
    refresh.add_argument(
        "--only",
        help="Comma-separated task keys instead of the full sequence",
    )
    refresh.add_argument(
        "--list", action="store_true", help="Print the available tasks and stop"
    )

    args = parser.parse_args(argv)

    if args.command == "refresh":
        if args.list:
            for key, task in admin_tasks.TASKS.items():
                marker = "*" if key in admin_tasks.SEQUENCE else " "
                print(f" {marker} {key:14} {task.label}")
            print("\n * included in a full refresh, in the order shown above")
            return 0

        keys = (
            [k.strip() for k in args.only.split(",") if k.strip()]
            if args.only
            else list(admin_tasks.SEQUENCE)
        )
        unknown = [k for k in keys if k not in admin_tasks.TASKS]
        if unknown:
            print(f"Unknown task(s): {', '.join(unknown)}", file=sys.stderr)
            return 2

        if not wait_for_database():
            return 1

        # Runs are recorded exactly as they are from the console, so a
        # scheduled refresh and a hand-started one read the same in the history.
        admin_tasks.run_sequence(keys)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
