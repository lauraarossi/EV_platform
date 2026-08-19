"""Accounts, sessions, and keeping one person's data away from another's."""
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.session import get_db
from app.main import app
from app.models import User
from app.security import create_session_token, hash_password, read_session_token, verify_password


# --- passwords --------------------------------------------------------------

def test_password_round_trip():
    h = hash_password("correct horse battery")
    assert h != "correct horse battery"          # never stored in the clear
    assert verify_password("correct horse battery", h)
    assert not verify_password("wrong", h)


def test_short_passwords_rejected():
    with pytest.raises(ValueError, match="at least"):
        hash_password("short")


def test_overlong_password_rejected_rather_than_silently_truncated():
    """bcrypt ignores anything past 72 bytes; accepting it would mean two
    different long passwords opening the same account."""
    with pytest.raises(ValueError, match="too long"):
        hash_password("a" * 73)


def test_google_only_account_cannot_be_password_guessed():
    assert not verify_password("anything", None)


# --- sessions ---------------------------------------------------------------

def test_session_token_round_trip(db):
    user = User(email="a@b.com")
    db.add(user)
    db.commit()
    assert read_session_token(create_session_token(user)) == user.id


def test_tampered_token_is_refused(db):
    user = User(email="a@b.com")
    db.add(user)
    db.commit()
    token = create_session_token(user)
    assert read_session_token(token[:-3] + "xyz") is None
    assert read_session_token("nonsense") is None


def test_token_signed_with_another_key_is_refused(db, monkeypatch):
    """Rotating SECRET_KEY must invalidate every existing session."""
    user = User(email="a@b.com")
    db.add(user)
    db.commit()
    token = create_session_token(user)

    monkeypatch.setattr(settings, "secret_key", "a-different-secret")
    assert read_session_token(token) is None


# --- registration and sign-in ----------------------------------------------

def test_register_signs_you_in(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "Laura@Example.com", "password": "correct horse battery"},
    )
    assert r.status_code == 201
    assert r.json()["email"] == "laura@example.com"      # normalised
    assert settings.session_cookie_name in r.cookies
    assert client.get("/api/v1/auth/me").status_code == 200


def test_session_cookie_is_httponly(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "a@b.com", "password": "correct horse battery"},
    )
    cookie = r.headers["set-cookie"].lower()
    # Script on the page must not be able to read the session.
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


def test_duplicate_email_is_rejected(client, signed_in):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "LAURA@example.com", "password": "another password"},
    )
    assert r.status_code == 409


def test_login_with_correct_password(client, signed_in):
    client.post("/api/v1/auth/logout")
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "laura@example.com", "password": "correct horse battery"},
    )
    assert r.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 200


@pytest.mark.parametrize(
    "email,password",
    [("laura@example.com", "wrong"), ("nobody@example.com", "correct horse battery")],
)
def test_bad_sign_in_gives_the_same_answer_either_way(client, signed_in, email, password):
    """A different message for an unknown email would let someone discover
    which addresses have accounts."""
    client.post("/api/v1/auth/logout")
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 401
    assert r.json()["detail"] == "Wrong email or password"


def test_logout_ends_the_session(client, signed_in):
    assert client.get("/api/v1/auth/me").status_code == 200
    client.post("/api/v1/auth/logout")
    assert client.get("/api/v1/auth/me").status_code == 401


def test_registration_can_be_closed(client, monkeypatch):
    monkeypatch.setattr(settings, "allow_registration", False)
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "gatecrasher@example.com", "password": "correct horse battery"},
    )
    assert r.status_code == 403


def test_options_hides_google_when_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "")
    body = client.get("/api/v1/auth/options").json()
    assert body["google_enabled"] is False
    assert body["google_client_id"] is None


def test_google_endpoint_refuses_when_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "")
    assert client.post("/api/v1/auth/google", json={"credential": "x"}).status_code == 503


def test_google_rejects_an_unverifiable_credential(client, monkeypatch):
    """A forged token must not get anyone in."""
    monkeypatch.setattr(settings, "google_client_id", "test-client-id.apps.googleusercontent.com")
    r = client.post("/api/v1/auth/google", json={"credential": "not.a.real.token"})
    assert r.status_code == 401


def google_claims(**over):
    """What Google's ID token carries, once verified."""
    return {
        "sub": "108000000000000000001",
        "email": "laura@example.com",
        "email_verified": True,
        "name": "Laura",
        "picture": "https://lh3.googleusercontent.com/a/photo",
    } | over


def accept_google(monkeypatch, **over):
    """Stand in for Google's signature check, which is exercised separately."""
    monkeypatch.setattr(settings, "google_client_id", "test-client.apps.googleusercontent.com")
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.verify_google_id_token",
        lambda credential: google_claims(**over),
    )


def test_google_creates_an_account_and_signs_it_in(client, db, monkeypatch):
    accept_google(monkeypatch)
    r = client.post("/api/v1/auth/google", json={"credential": "signed.by.google"})

    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "laura@example.com"
    assert body["has_google"] is True and body["has_password"] is False
    assert body["display_name"] == "Laura"
    # The session cookie is set, so the next call is already authenticated.
    assert client.get("/api/v1/auth/me").json()["email"] == "laura@example.com"


def test_google_links_to_an_existing_password_account(client, db, monkeypatch):
    """Otherwise the same person ends up with two accounts and their vehicles
    split across them. Safe only because Google says the address is verified."""
    client.post("/api/v1/auth/register",
                json={"email": "laura@example.com", "password": "correct horse battery"})
    client.post("/api/v1/auth/logout")

    accept_google(monkeypatch)
    r = client.post("/api/v1/auth/google", json={"credential": "signed.by.google"})

    assert r.status_code == 200
    assert r.json()["has_password"] is True and r.json()["has_google"] is True
    assert db.query(User).count() == 1


def test_google_matches_an_existing_address_case_insensitively(client, db, monkeypatch):
    client.post("/api/v1/auth/register",
                json={"email": "laura@example.com", "password": "correct horse battery"})
    accept_google(monkeypatch, email="Laura@Example.COM")
    client.post("/api/v1/auth/google", json={"credential": "signed.by.google"})
    assert db.query(User).count() == 1


def test_google_returning_signs_into_the_same_account(client, db, monkeypatch):
    accept_google(monkeypatch)
    client.post("/api/v1/auth/google", json={"credential": "signed.by.google"})
    # A second visit, after the address changed on Google's side: the stable
    # subject id is what identifies the account, not the email.
    accept_google(monkeypatch, email="laura.new@example.com")
    r = client.post("/api/v1/auth/google", json={"credential": "signed.by.google"})

    assert r.status_code == 200
    assert db.query(User).count() == 1


def test_google_refuses_an_unverified_address(client, db, monkeypatch):
    """Without this, anyone able to set an unverified address on a Google
    account could claim someone else's account here by email."""
    accept_google(monkeypatch, email_verified=False)
    r = client.post("/api/v1/auth/google", json={"credential": "signed.by.google"})

    assert r.status_code == 401
    assert db.query(User).count() == 0


def test_google_respects_closed_registration(client, db, monkeypatch):
    accept_google(monkeypatch)
    monkeypatch.setattr(settings, "allow_registration", False)
    r = client.post("/api/v1/auth/google", json={"credential": "signed.by.google"})

    assert r.status_code == 403
    assert db.query(User).count() == 0


def test_google_refuses_a_disabled_account(client, db, monkeypatch):
    accept_google(monkeypatch)
    client.post("/api/v1/auth/google", json={"credential": "signed.by.google"})
    db.query(User).one().is_active = False
    db.commit()

    assert client.post("/api/v1/auth/google",
                       json={"credential": "signed.by.google"}).status_code == 403


def test_google_sign_in_grants_the_admin_role(client, db, monkeypatch):
    """The admin bootstrap has to work for whichever way you sign in."""
    accept_google(monkeypatch)
    monkeypatch.setattr(settings, "admin_emails", "laura@example.com")
    r = client.post("/api/v1/auth/google", json={"credential": "signed.by.google"})
    assert r.json()["is_admin"] is True


# --- everything else needs an account --------------------------------------

@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/vehicles/"),
        ("get", "/api/v1/fuel-events/"),
        ("get", "/api/v1/tariffs/"),
        ("get", "/api/v1/catalog/makes"),
        ("get", "/api/v1/fuel-prices/"),
        ("get", "/api/v1/stats/vehicles/1/summary"),
    ],
)
def test_signed_out_callers_are_refused(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_health_stays_open(client):
    assert client.get("/api/v1/health").status_code == 200


# --- one person cannot reach another's data --------------------------------

def make_vehicle(client, make="Renault"):
    r = client.post(
        "/api/v1/vehicles/",
        json={"make": make, "model": "R4 E-Tech", "year": 2026, "fuel_type": "electric",
              "battery_capacity_kwh": 52, "is_owned": True},
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def other_client(db):
    """A second signed-in account sharing the same database."""
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    r = c.post(
        "/api/v1/auth/register",
        json={"email": "someone.else@example.com", "password": "another password"},
    )
    assert r.status_code == 201, r.text
    return c


def test_vehicles_are_private(client, signed_in, other_client):
    mine = make_vehicle(client)
    theirs = make_vehicle(other_client, make="Nissan")

    assert [v["id"] for v in client.get("/api/v1/vehicles/").json()] == [mine["id"]]
    assert [v["id"] for v in other_client.get("/api/v1/vehicles/").json()] == [theirs["id"]]


def test_cannot_read_someone_elses_vehicle(client, signed_in, other_client):
    theirs = make_vehicle(other_client, make="Nissan")
    # 404 rather than 403: a 403 would confirm the record exists.
    assert client.get(f"/api/v1/vehicles/{theirs['id']}").status_code == 404


def test_cannot_edit_or_delete_someone_elses_vehicle(client, signed_in, other_client):
    theirs = make_vehicle(other_client, make="Nissan")
    payload = {"make": "Hijacked", "model": "X", "year": 2026, "fuel_type": "electric",
               "is_owned": True}
    assert client.put(f"/api/v1/vehicles/{theirs['id']}", json=payload).status_code == 404
    assert client.delete(f"/api/v1/vehicles/{theirs['id']}").status_code == 404
    # still intact for its owner
    assert other_client.get(f"/api/v1/vehicles/{theirs['id']}").json()["make"] == "Nissan"


def test_cannot_log_a_charge_against_someone_elses_vehicle(client, signed_in, other_client):
    theirs = make_vehicle(other_client, make="Nissan")
    r = client.post(
        "/api/v1/fuel-events/",
        json={"vehicle_id": theirs["id"], "date": "2026-08-01", "odometer_km": 100,
              "energy_kwh": 10, "charger_type": "ac_home"},
    )
    assert r.status_code == 404


def test_charges_are_private(client, signed_in, other_client):
    mine = make_vehicle(client)
    theirs = make_vehicle(other_client, make="Nissan")
    for c, v in ((client, mine), (other_client, theirs)):
        c.post("/api/v1/fuel-events/", json={
            "vehicle_id": v["id"], "date": "2026-08-01", "odometer_km": 100,
            "energy_kwh": 10, "charger_type": "ac_home"})

    assert len(client.get("/api/v1/fuel-events/").json()) == 1
    assert len(other_client.get("/api/v1/fuel-events/").json()) == 1


def test_cannot_read_someone_elses_stats(client, signed_in, other_client):
    theirs = make_vehicle(other_client, make="Nissan")
    assert client.get(f"/api/v1/stats/vehicles/{theirs['id']}/summary").status_code == 404


def test_tariffs_are_private(client, signed_in, other_client):
    body = {"name": "Night Saver", "effective_from": "2026-01-01",
            "rates": [{"name": "Flat", "start_time": "00:00", "end_time": "00:00",
                       "price_per_kwh": 0.3}]}
    assert client.post("/api/v1/tariffs/", json=body).status_code == 201

    assert len(client.get("/api/v1/tariffs/").json()) == 1
    assert other_client.get("/api/v1/tariffs/").json() == []


# --- one canonical hostname ---------------------------------------------------

def test_www_redirects_to_the_bare_domain(client):
    """A cookie set on the apex is not sent to www, so signing in on one would
    look like being signed out on the other."""
    r = client.get("/garage", headers={"host": "www.eevie.ie"}, follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"].endswith("://eevie.ie/garage")


def test_the_redirect_keeps_the_path_and_query(client):
    r = client.get(
        "/api/v1/catalog/models?make_key=renault",
        headers={"host": "www.eevie.ie"},
        follow_redirects=False,
    )
    assert r.status_code == 301
    assert r.headers["location"].endswith("://eevie.ie/api/v1/catalog/models?make_key=renault")


def test_the_bare_domain_is_left_alone(client):
    """Only www is redirected — everything else must pass straight through."""
    r = client.get("/api/v1/health", headers={"host": "eevie.ie"})
    assert r.status_code == 200


def test_the_redirect_does_not_need_an_account(client):
    """It runs outside the auth middleware, so it answers before anything asks
    who you are."""
    r = client.get("/api/v1/vehicles/", headers={"host": "www.eevie.ie"},
                   follow_redirects=False)
    assert r.status_code == 301


def test_rs256_verification_is_actually_available():
    """PyJWT installs happily without `cryptography` and only fails when it
    first meets a real Google token — which is signed RS256.

    That is what happened: the package was present locally as someone else's
    dependency and absent from the image, so every test passed while the
    deployed sign-in returned "RS256 requires 'cryptography' to be installed".
    """
    from jwt.api_jws import get_default_algorithms

    assert "RS256" in get_default_algorithms()
