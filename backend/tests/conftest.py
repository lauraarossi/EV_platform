import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import app
from app.models import Base


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def client(db):
    """A client whose requests hit the same in-memory database as `db`."""
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def signed_in(client):
    """Register an account; the client keeps the session cookie afterwards."""
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "laura@example.com", "password": "correct horse battery"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def register_other(client_factory, email="someone@example.com"):
    """A second account, for checking one person can't see another's data."""
    c = client_factory()
    r = c.post("/api/v1/auth/register", json={"email": email, "password": "another password"})
    assert r.status_code == 201, r.text
    return c, r.json()


@pytest.fixture
def user(db):
    """A bare account for tests that exercise services directly."""
    from app.models import User

    u = User(email="owner@example.com")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def ensure_user(db):
    """Get or make an owner — data can't exist without one now."""
    from app.models import User

    existing = db.query(User).first()
    if existing:
        return existing
    u = User(email="owner@example.com")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u
