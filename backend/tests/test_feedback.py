"""Taking feedback from whoever has something to say.

Open on purpose: the person deciding whether to bother signing up has the
report most worth hearing, and asking them to make an account first is how you
never hear it. That openness is what the rest of this has to defend against.
"""
import pytest

from app.api.v1.endpoints import feedback as endpoint
from app.models import Feedback, FeedbackStatus, User, UserRole


@pytest.fixture(autouse=True)
def clear_rate_limit():
    endpoint._recent.clear()
    yield
    endpoint._recent.clear()


def make_admin(db, email="laura@example.com"):
    user = db.query(User).filter(User.email == email).one()
    user.role = UserRole.admin
    db.commit()
    return user


# --- leaving it ---------------------------------------------------------------

def test_a_signed_out_visitor_can_leave_feedback(client, db):
    r = client.post("/api/v1/feedback/", json={"message": "the compare page confused me"})

    assert r.status_code == 201
    item = db.query(Feedback).one()
    assert item.message == "the compare page confused me"
    assert item.user_id is None
    assert item.status == FeedbackStatus.new


def test_the_page_they_were_on_is_kept(db, client):
    """"The numbers look wrong" is what people write. Where they were is what
    makes it actionable."""
    client.post("/api/v1/feedback/", json={"message": "numbers look wrong", "page": "/stats"})
    assert db.query(Feedback).one().page == "/stats"


def test_a_signed_in_report_is_attached_to_the_account(client, signed_in, db):
    client.post("/api/v1/feedback/", json={"message": "wishlist: trip tags"})

    item = db.query(Feedback).one()
    assert item.user_id == db.query(User).one().id
    assert item.email == "laura@example.com"


def test_the_browser_is_recorded(client, db):
    client.post("/api/v1/feedback/", json={"message": "layout breaks"},
                headers={"user-agent": "Mozilla/5.0 (iPhone)"})
    assert "iPhone" in db.query(Feedback).one().user_agent


def test_an_empty_message_is_refused(client, db):
    assert client.post("/api/v1/feedback/", json={"message": "   "}).status_code == 422
    assert db.query(Feedback).count() == 0


def test_a_very_long_message_is_refused_rather_than_truncated(client, db):
    r = client.post("/api/v1/feedback/", json={"message": "x" * 5000})
    assert r.status_code == 422
    assert db.query(Feedback).count() == 0


# --- keeping the bots out -----------------------------------------------------

def test_the_honeypot_swallows_a_bot(client, db):
    """Accepted so far as the bot can tell. Telling it that it was spotted only
    teaches whoever wrote it."""
    r = client.post("/api/v1/feedback/", json={"message": "buy cheap watches", "website": "http://spam"})

    assert r.status_code == 201
    assert db.query(Feedback).count() == 0


def test_a_flood_from_one_address_is_cut_off(client, db):
    for i in range(endpoint.MAX_PER_HOUR):
        assert client.post("/api/v1/feedback/", json={"message": f"note {i}"}).status_code == 201

    r = client.post("/api/v1/feedback/", json={"message": "and another"})
    assert r.status_code == 429
    assert db.query(Feedback).count() == endpoint.MAX_PER_HOUR


def test_the_limit_is_a_moving_hour_not_a_lifetime_ban(db):
    ip = "203.0.113.9"
    now = 1_000_000.0
    for _ in range(endpoint.MAX_PER_HOUR):
        assert endpoint._rate_limited(ip, now) is False
    assert endpoint._rate_limited(ip, now) is True

    # An hour later the earlier ones no longer count.
    assert endpoint._rate_limited(ip, now + 3601) is False


# --- reading it ---------------------------------------------------------------

def test_feedback_is_admin_only(client, signed_in):
    assert client.get("/api/v1/admin/feedback").status_code == 403


def test_an_admin_sees_it_newest_first(client, signed_in, db):
    make_admin(db)
    for msg in ("first", "second", "third"):
        client.post("/api/v1/feedback/", json={"message": msg})

    rows = client.get("/api/v1/admin/feedback").json()
    assert [r["message"] for r in rows] == ["third", "second", "first"]


def test_the_overview_counts_what_has_not_been_read(client, signed_in, db):
    make_admin(db)
    client.post("/api/v1/feedback/", json={"message": "something"})
    assert client.get("/api/v1/admin/overview").json()["feedback_new"] == 1

    item_id = client.get("/api/v1/admin/feedback").json()[0]["id"]
    client.patch(f"/api/v1/admin/feedback/{item_id}", json={"status": "read"})
    assert client.get("/api/v1/admin/overview").json()["feedback_new"] == 0


def test_it_can_be_filtered_to_what_is_still_outstanding(client, signed_in, db):
    make_admin(db)
    client.post("/api/v1/feedback/", json={"message": "one"})
    client.post("/api/v1/feedback/", json={"message": "two"})
    first = client.get("/api/v1/admin/feedback").json()[0]["id"]
    client.patch(f"/api/v1/admin/feedback/{first}", json={"status": "done"})

    assert len(client.get("/api/v1/admin/feedback?status=new").json()) == 1
    assert len(client.get("/api/v1/admin/feedback?status=done").json()) == 1


def test_nothing_is_deleted(client, signed_in, db):
    """A report that turned out to be nothing is still evidence of what
    confused somebody."""
    make_admin(db)
    assert not any(
        route.methods == {"DELETE"} and "feedback" in route.path
        for route in client.app.routes
        if hasattr(route, "methods") and hasattr(route, "path")
    )


def test_a_missing_item_is_a_404(client, signed_in, db):
    make_admin(db)
    assert client.patch("/api/v1/admin/feedback/999", json={"status": "read"}).status_code == 404
