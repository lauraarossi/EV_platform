"""Surviving a database that sleeps.

Railway's serverless Postgres stops when idle and boots on the first
connection. Both halves of that have taken the app down: a pooled connection
is dead once the server stopped, and a fresh one during the boot is refused
outright. Either surfaced as a 500 on whichever request happened to be first,
which is why signing in with Google failed once and then worked.
"""
import pytest

from app.db import session as db_session


class FakeDialect:
    """Stands in for the driver, so the retry can be tested without a server."""

    def __init__(self, failures, message="the database system is starting up"):
        self.calls = 0
        self.failures = failures
        self.message = message

        outer = self

        class dbapi:  # noqa: N801 — mirrors SQLAlchemy's attribute name
            @staticmethod
            def connect(*args, **kwargs):
                outer.calls += 1
                if outer.calls <= outer.failures:
                    raise OSError(outer.message)
                return "a connection"

        self.dbapi = dbapi


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(db_session.time, "sleep", lambda s: None)


def test_a_booting_database_is_waited_for(monkeypatch):
    dialect = FakeDialect(failures=2)
    assert db_session._retry_while_waking(dialect, None, (), {}) == "a connection"
    assert dialect.calls == 3


def test_a_real_failure_is_raised_at_once(monkeypatch):
    """Not everything is a wake. A wrong password or a missing host should fail
    now, with its own message, rather than after five slow retries."""
    dialect = FakeDialect(failures=99, message="password authentication failed")

    with pytest.raises(OSError, match="password authentication failed"):
        db_session._retry_while_waking(dialect, None, (), {})
    assert dialect.calls == 1


def test_a_refused_connection_is_not_treated_as_a_wake(monkeypatch):
    dialect = FakeDialect(failures=99, message="Connection refused")

    with pytest.raises(OSError, match="Connection refused"):
        db_session._retry_while_waking(dialect, None, (), {})
    assert dialect.calls == 1


def test_it_gives_up_rather_than_holding_a_request_open(monkeypatch):
    """A request cannot sit for minutes. If the database is genuinely gone the
    error should be the honest one."""
    dialect = FakeDialect(failures=99)

    with pytest.raises(OSError, match="starting up"):
        db_session._retry_while_waking(dialect, None, (), {})
    assert dialect.calls == db_session.CONNECT_ATTEMPTS


@pytest.mark.parametrize(
    "message",
    [
        "the database system is starting up",
        "The database system is STARTING UP",
        "server is not yet accepting connections",
        "the database system is in recovery mode",
    ],
)
def test_the_phrases_postgres_uses_while_waking(message):
    dialect = FakeDialect(failures=1, message=message)
    assert db_session._retry_while_waking(dialect, None, (), {}) == "a connection"


def test_pooled_connections_are_checked_before_reuse():
    """The other half: after a sleep the pool is full of dead connections, and
    without this the first request to reuse one fails."""
    assert db_session.engine.pool._pre_ping is True
