"""The admin console: who can reach it, and what it can and cannot do."""
import pytest

from app.config import settings
from app.models import ImportRun, ImportStatus, User, UserRole
from app.services import admin_tasks

ADMIN_ROUTES = [
    ("get", "/api/v1/admin/overview"),
    ("get", "/api/v1/admin/runs"),
    ("get", "/api/v1/admin/users"),
]


def make_admin(db, email="laura@example.com"):
    user = db.query(User).filter(User.email == email).one()
    user.role = UserRole.admin
    db.commit()
    return user


# --- access ------------------------------------------------------------------

@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_signed_out_callers_are_refused(client, method, path):
    assert getattr(client, method)(path).status_code == 401


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_an_ordinary_account_is_refused(client, signed_in, method, path):
    """Registering does not make you an admin."""
    assert getattr(client, method)(path).status_code == 403


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_an_admin_gets_in(client, signed_in, db, method, path):
    make_admin(db)
    assert getattr(client, method)(path).status_code == 200


def test_a_new_account_is_not_an_admin(client, signed_in):
    assert client.get("/api/v1/auth/me").json()["is_admin"] is False


def test_running_a_task_needs_the_role(client, signed_in):
    r = client.post("/api/v1/admin/tasks/rekey/run")
    assert r.status_code == 403


def test_every_admin_route_is_gated():
    """The dependency is on the router, so this holds for routes added later
    without anyone remembering to decorate them."""
    from app.api.v1.endpoints.admin import router

    assert any(
        getattr(d.dependency, "__name__", "") == "get_current_admin"
        for d in router.dependencies
    )


# --- the console's own data ---------------------------------------------------

def test_overview_counts_what_is_there(client, signed_in, db):
    make_admin(db)
    body = client.get("/api/v1/admin/overview").json()

    assert body["users"] == 1 and body["admins"] == 1
    assert body["catalogue_total"] == 0
    # Every refresh is offered, whether or not it has ever run.
    assert {t["key"] for t in body["tasks"]} == set(admin_tasks.TASKS)
    assert all(t["last_run"] is None for t in body["tasks"])


def test_overview_counts_models_not_spellings(client, signed_in, db):
    """Three sources spelling one car three ways is one model, not three."""
    from app.models import CatalogSource, CatalogVehicle, FuelType

    for i, (make, model, source) in enumerate([
        ("RENAULT", "ZOE", CatalogSource.eea),
        ("Renault", "Zoe", CatalogSource.evdb),
        ("Renault", "New ZOE", CatalogSource.vca),
    ]):
        db.add(CatalogVehicle(
            id=f"row-{i}", source=source, make=make, model=model,
            variant=model, fuel_type=FuelType.electric,
        ))
    db.commit()

    make_admin(db)
    body = client.get("/api/v1/admin/overview").json()
    assert body["catalogue_total"] == 3
    assert body["distinct_makes"] == 1
    assert body["distinct_models"] == 1


def test_the_user_list_shows_roles_but_not_anyone_s_cars(client, signed_in, db):
    make_admin(db)
    rows = client.get("/api/v1/admin/users").json()
    assert [r["email"] for r in rows] == ["laura@example.com"]
    assert rows[0]["role"] == "admin"
    assert rows[0]["vehicles"] == 0
    # A count only — the console has no route to what someone drives.
    assert "vehicle_list" not in rows[0]


# --- refreshes ---------------------------------------------------------------

def test_starting_a_run_returns_immediately(client, signed_in, db, monkeypatch):
    """202, not 200: accepted rather than finished. A synchronous EEA import
    would outlast the proxy in front of it."""
    make_admin(db)
    # The background half is covered below, against the test's own session;
    # left alone here it would open a real one and work on the live database.
    monkeypatch.setattr(admin_tasks, "execute", lambda *a, **k: None)
    r = client.post("/api/v1/admin/tasks/rekey/run")

    assert r.status_code == 202
    assert r.json()["task"] == "rekey"
    assert r.json()["status"] == "running"


def test_a_completed_run_records_its_result(db):
    run = admin_tasks.start(db, "rekey", None)
    admin_tasks.execute(run.id, "rekey", session_factory=lambda: _NoCloseSession(db))

    db.refresh(run)
    assert run.status == ImportStatus.ok
    assert run.result == {"rows": 0, "changed": 0}
    assert run.finished_at is not None and run.duration_ms is not None


def test_an_unknown_task_is_a_404(client, signed_in, db):
    make_admin(db)
    assert client.post("/api/v1/admin/tasks/nonsense/run").status_code == 404


def test_a_failing_refresh_is_recorded_rather_than_lost(db, monkeypatch):
    """A source quietly failing for a month is the thing this must surface:
    the catalogue looks fine either way, since the old rows are still there."""
    def explode(db, params):
        raise RuntimeError("the source moved")

    monkeypatch.setitem(
        admin_tasks.TASKS, "evdb",
        admin_tasks.Task("evdb", "EV database", "", explode),
    )
    run = admin_tasks.start(db, "evdb", None)
    admin_tasks.execute(run.id, "evdb", session_factory=lambda: _NoCloseSession(db))

    db.refresh(run)
    assert run.status == ImportStatus.failed
    assert "the source moved" in run.error
    assert run.finished_at is not None


def test_two_runs_of_one_task_do_not_overlap(client, signed_in, db):
    make_admin(db)
    db.add(ImportRun(
        task="eea", status=ImportStatus.running,
        started_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    ))
    db.commit()

    r = client.post("/api/v1/admin/tasks/eea/run")
    assert r.status_code == 409


# --- roles -------------------------------------------------------------------

def test_an_admin_can_promote_someone(client, signed_in, db):
    make_admin(db)
    other = User(email="friend@example.com", password_hash="x")
    db.add(other)
    db.commit()

    r = client.patch(f"/api/v1/admin/users/{other.id}/role", json={"role": "admin"})
    assert r.status_code == 200 and r.json()["role"] == "admin"


def test_the_last_admin_cannot_lock_everyone_out(client, signed_in, db):
    """Stepping down would leave nobody able to reach this endpoint to undo it."""
    admin = make_admin(db)
    r = client.patch(f"/api/v1/admin/users/{admin.id}/role", json={"role": "user"})
    assert r.status_code == 409

    db.add(User(email="second@example.com", password_hash="x", role=UserRole.admin))
    db.commit()
    r = client.patch(f"/api/v1/admin/users/{admin.id}/role", json={"role": "user"})
    assert r.status_code == 200


# --- granting the role from the environment ----------------------------------

def test_a_listed_email_becomes_an_admin_on_sign_in(client, db, monkeypatch):
    """How the first admin exists at all on a hosted deployment, where there is
    no shell to promote an account from."""
    monkeypatch.setattr(settings, "admin_emails", "boss@example.com")
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "boss@example.com", "password": "correct horse battery"},
    )
    assert r.status_code == 201
    assert r.json()["is_admin"] is True


def test_an_unlisted_email_does_not(client, db, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "boss@example.com")
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "someone@example.com", "password": "correct horse battery"},
    )
    assert r.json()["is_admin"] is False


def test_removing_an_email_does_not_demote(db, monkeypatch):
    """Otherwise a typo in an environment variable locks the console."""
    from app.security import apply_admin_policy

    user = User(email="boss@example.com", password_hash="x", role=UserRole.admin)
    monkeypatch.setattr(settings, "admin_emails", "")
    assert apply_admin_policy(user) is False
    assert user.role == UserRole.admin


def test_existing_accounts_are_promoted_at_startup(db, monkeypatch):
    """A live session never passes through sign-in, and would otherwise wait
    out a thirty-day cookie before picking the role up."""
    from app.security import sync_admin_roles

    db.add(User(email="boss@example.com", password_hash="x"))
    db.commit()

    monkeypatch.setattr(settings, "admin_emails", "BOSS@example.com")
    assert sync_admin_roles(db) == 1
    assert db.query(User).filter(User.email == "boss@example.com").one().is_admin


class _NoCloseSession:
    """Hands the test's session to code that manages its own, without letting
    the context manager close it out from under the test."""

    def __init__(self, session):
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, *exc):
        return False
