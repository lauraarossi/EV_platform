"""Exchange rates, so money can be shown in the currency someone actually uses.

The series is stored rather than a single current figure, for the same reason
the fuel prices are: a charge from March should convert at March's rate.
"""
import datetime

import pytest

from app.models import ExchangeRate, User
from app.services import fx

D = datetime.date


def payload(date="2026-08-18", **rates):
    return {"amount": 1.0, "base": "EUR", "date": date,
            "rates": rates or {"GBP": 0.85585, "USD": 1.1576}}


# --- storing ------------------------------------------------------------------

def test_a_day_of_rates_is_stored(db):
    result = fx.ingest(db, data=payload())
    assert result.inserted == 2 and result.latest_date == "2026-08-18"
    assert db.query(ExchangeRate).count() == 2


def test_the_day_stored_is_the_one_published(db):
    """The ECB publishes on working days only, so a weekend request answers
    with Friday's — the response carries its own date for that reason."""
    fx.ingest(db, data=payload(date="2026-08-14"))
    assert db.query(ExchangeRate).first().date == D(2026, 8, 14)


def test_reimporting_a_day_revises_rather_than_duplicates(db):
    fx.ingest(db, data=payload(GBP=0.85))
    result = fx.ingest(db, data=payload(GBP=0.86))
    assert result.inserted == 0 and result.updated == 1
    assert db.query(ExchangeRate).count() == 1
    assert db.query(ExchangeRate).one().rate == 0.86


def test_an_empty_response_is_refused(db):
    """Storing nothing quietly would leave the app converting at stale rates
    while the console reported a successful refresh."""
    with pytest.raises(ValueError, match="no rates"):
        fx.ingest(db, data={"base": "EUR", "date": "2026-08-18", "rates": {}})


# --- looking up ---------------------------------------------------------------

def test_a_rate_is_found_from_before_the_date_asked_for(db):
    """There are no weekends in the series, so an exact-date lookup would miss
    two days in seven."""
    fx.ingest(db, data=payload(date="2026-08-14", GBP=0.85))
    found = fx.rate_on(db, "GBP", D(2026, 8, 16))       # a Sunday
    assert found == (0.85, D(2026, 8, 14))


def test_a_past_date_gets_the_rate_of_its_own_time(db):
    fx.ingest(db, data=payload(date="2026-03-16", GBP=0.86408))
    fx.ingest(db, data=payload(date="2026-08-18", GBP=0.85585))

    assert fx.rate_on(db, "GBP", D(2026, 3, 20))[0] == 0.86408
    assert fx.rate_on(db, "GBP", D(2026, 8, 20))[0] == 0.85585


def test_the_base_needs_no_rate(db):
    assert fx.rate_on(db, "EUR", D(2026, 8, 18))[0] == 1.0


def test_an_unknown_currency_has_no_rate(db):
    assert fx.rate_on(db, "JPY") is None
    assert fx.convert(db, 100.0, "JPY") is None


def test_converting_uses_the_rate_for_that_day(db):
    fx.ingest(db, data=payload(date="2026-03-16", GBP=0.86408))
    fx.ingest(db, data=payload(date="2026-08-18", GBP=0.85585))

    assert fx.convert(db, 100.0, "GBP", D(2026, 3, 20)) == 86.41
    assert fx.convert(db, 100.0, "GBP", D(2026, 8, 20)) == 85.58


def test_latest_rates_carries_the_base_itself(db):
    fx.ingest(db, data=payload())
    rates = fx.latest_rates(db)
    assert rates["EUR"] == 1.0 and rates["GBP"] == 0.85585
    assert "JPY" not in rates          # nothing is invented


# --- the preference -----------------------------------------------------------

def test_the_currency_is_offered_with_its_rates(client, signed_in, db):
    fx.ingest(db, data=payload())
    body = client.get("/api/v1/currency/").json()

    assert body["base"] == "EUR"
    assert body["rates"]["GBP"] == 0.85585
    assert {c["code"] for c in body["choices"]} >= {"EUR", "GBP", "USD"}


def test_choosing_a_currency_sticks_to_the_account(client, signed_in, db):
    """Not to the browser, unlike the unit system: it decides how the money
    someone entered is read back, so it should follow them between devices."""
    fx.ingest(db, data=payload())
    assert client.put("/api/v1/currency/", json={"currency": "gbp"}).status_code == 200
    assert client.get("/api/v1/auth/me").json()["currency"] == "GBP"
    assert db.query(User).one().currency == "GBP"


def test_a_currency_with_no_rate_yet_is_refused(client, signed_in):
    """Better a clear refusal than every figure silently reading as euros."""
    r = client.put("/api/v1/currency/", json={"currency": "USD"})
    assert r.status_code == 409


def test_an_unsupported_currency_is_refused(client, signed_in):
    assert client.put("/api/v1/currency/", json={"currency": "XYZ"}).status_code == 422


def test_the_base_can_always_be_chosen(client, signed_in):
    assert client.put("/api/v1/currency/", json={"currency": "EUR"}).status_code == 200
