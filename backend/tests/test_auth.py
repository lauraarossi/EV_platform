"""Optional basic auth.

The important property is that it is *off* unless a password is configured, so
enabling it can never be an accident and local development is untouched.
"""
import base64

import pytest
from app.config import settings


@pytest.fixture
def protected(monkeypatch):
    monkeypatch.setattr(settings, "app_username", "eevie")
    monkeypatch.setattr(settings, "app_password", "hunter2")


def auth_header(user: str, password: str) -> dict:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_open_when_no_password_is_set(client, monkeypatch):
    monkeypatch.setattr(settings, "app_password", "")
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/auth/options").status_code == 200


def test_challenges_when_password_is_set(client, protected):
    r = client.get("/api/v1/auth/options")
    assert r.status_code == 401
    # Without this header the browser never shows a password prompt.
    assert r.headers["www-authenticate"].startswith("Basic")


def test_correct_credentials_pass(client, protected):
    r = client.get("/api/v1/auth/options", headers=auth_header("eevie", "hunter2"))
    assert r.status_code == 200


@pytest.mark.parametrize(
    "user,password",
    [("eevie", "wrong"), ("wrong", "hunter2"), ("wrong", "wrong"), ("", "")],
)
def test_wrong_credentials_rejected(client, protected, user, password):
    assert client.get("/api/v1/auth/options", headers=auth_header(user, password)).status_code == 401


@pytest.mark.parametrize(
    "header",
    ["", "Basic", "Basic !!!not-base64!!!", "Bearer abc123", "Basic " + base64.b64encode(b"no-colon").decode()],
)
def test_malformed_headers_rejected_without_erroring(client, protected, header):
    r = client.get("/api/v1/auth/options", headers={"Authorization": header} if header else {})
    assert r.status_code == 401


def test_health_stays_open_so_deploys_dont_flap(client, protected):
    """The platform health check is unauthenticated; if this 401s the service
    is marked unhealthy and restarted in a loop."""
    assert client.get("/api/v1/health").status_code == 200


def test_protects_the_frontend_too_not_just_the_api(client, protected):
    """Serving the SPA from the same process means one password covers both."""
    assert client.get("/garage").status_code == 401
    assert client.get("/docs").status_code == 401


# --- themed docs -------------------------------------------------------------

def test_docs_page_is_served(client):
    r = client.get("/docs")
    assert r.status_code == 200
    assert "swagger-ui" in r.text


def test_docs_carries_the_theme_toggle_and_shared_preference(client):
    body = client.get("/docs").text
    assert 'id="eevie-theme"' in body
    # Same storage key as the SPA, so switching in one place switches both.
    assert "ev-platform-theme" in body


def test_docs_sends_cookies_with_try_it_out(client):
    """Without withCredentials every Execute would come back 401."""
    assert "withCredentials: true" in client.get("/docs").text


def test_docs_is_behind_basic_auth_when_enabled(client, protected):
    assert client.get("/docs").status_code == 401
