"""The tools without an account.

Stateless by construction: a request carries the cars and the fill-ups, the
server does the arithmetic, and nothing is written down. That is what lets
someone try the thing before deciding whether to keep anything — and it is the
only part of the app a search engine can reach.
"""
import pytest

from app.models import CatalogVehicle, FuelEvent, FuelPrice, User, Vehicle

EV = {
    "make": "Renault", "model": "4 E-Tech", "fuel_type": "electric",
    "consumption_kwh_per_100km": 16.0,
}
PETROL = {
    "make": "Audi", "model": "A4", "fuel_type": "petrol",
    "fuel_consumption_l_per_100km": 7.0,
}
DIESEL = {
    "make": "Skoda", "model": "Octavia", "fuel_type": "diesel",
    "fuel_consumption_l_per_100km": 5.0,
}


def compare(client, first, second, **over):
    body = {"first": first, "second": second, "distance_km": 10_000,
            "price_per_litre": 1.80, "price_per_kwh": 0.28} | over
    return client.post("/api/v1/public/compare", json=body)


# --- no account needed --------------------------------------------------------

def test_a_visitor_can_compare_without_signing_in(client):
    r = compare(client, EV, PETROL)

    assert r.status_code == 200
    body = r.json()
    # 1,600 kWh at 0.28 against 700 L at 1.80.
    assert body["actual_cost"] == pytest.approx(448.0)
    assert body["alternative_cost"] == pytest.approx(1260.0)
    assert body["saving"] == pytest.approx(812.0)


def test_nothing_is_written_down(client, db):
    """The point of the whole arrangement: no account, no rows, nothing to
    delete afterwards."""
    compare(client, EV, PETROL)
    client.post("/api/v1/public/metrics", json={
        "vehicle": EV,
        "events": [
            {"date": "2026-06-01", "odometer_km": 10_000, "energy_kwh": 40, "cost": 11.2},
            {"date": "2026-06-14", "odometer_km": 10_300, "energy_kwh": 45, "cost": 12.6},
        ],
    })

    assert db.query(Vehicle).count() == 0
    assert db.query(FuelEvent).count() == 0
    assert db.query(User).count() == 0


@pytest.mark.parametrize(
    "first,second",
    [
        (EV, PETROL), (EV, DIESEL), (EV, EV),
        (PETROL, DIESEL), (PETROL, PETROL), (DIESEL, DIESEL),
        (PETROL, EV),
    ],
)
def test_every_pairing_of_fuels_works(client, first, second):
    """Both directions and both sides the same — an EV owner asking about
    diesel and a diesel owner asking about an EV are one question."""
    r = compare(client, first, second)
    assert r.status_code == 200
    assert r.json()["distance_km"] == 10_000


def test_two_identical_cars_come_out_level(client):
    body = compare(client, PETROL, PETROL).json()
    assert body["saving"] == 0.0
    assert body["co2_saving_kg"] == 0.0


# --- the rates in the form ----------------------------------------------------

def test_the_entered_prices_are_the_ones_used(client):
    """A signed-out visitor has no tariff and no receipts, so what they type is
    the best information available — and someone on a night rate must be able
    to say so."""
    cheap = compare(client, EV, PETROL, price_per_kwh=0.14).json()
    dear = compare(client, EV, PETROL, price_per_kwh=0.35).json()

    assert cheap["actual_cost"] == pytest.approx(224.0)     # 1,600 kWh at 0.14
    assert dear["actual_cost"] == pytest.approx(560.0)      # at 0.35


def test_suggested_prices_say_where_they_came_from(client, db):
    import datetime

    from app.models import FuelKind, PriceSource

    db.add(FuelPrice(date=datetime.date(2026, 8, 24), country="IE", region="",
                     fuel_kind=FuelKind.petrol_95, price_per_litre=1.799,
                     currency="EUR", source=PriceSource.eu_oil_bulletin))
    db.commit()

    body = client.get("/api/v1/public/prices").json()
    assert body["petrol"]["price_per_litre"] == 1.799
    assert body["petrol"]["as_of"] == "2026-08-24"
    assert "Oil Bulletin" in body["petrol"]["source"]
    # Named a suggestion, since a national weekly average is nobody's receipt.
    assert "change it to yours" in body["electricity"]["source"]


# --- a log held in a browser --------------------------------------------------

def test_metrics_are_worked_out_from_events_in_the_request(client):
    r = client.post("/api/v1/public/metrics", json={
        "vehicle": EV | {"battery_capacity_kwh": 52.0},
        "events": [
            {"date": "2026-06-01", "odometer_km": 10_000, "energy_kwh": 40,
             "cost": 11.2, "soc_start_pct": 20, "soc_end_pct": 80},
            {"date": "2026-06-14", "odometer_km": 10_300, "energy_kwh": 45,
             "cost": 12.6, "soc_start_pct": 20, "soc_end_pct": 80},
        ],
    })

    assert r.status_code == 200
    summary = r.json()["summary"]
    assert summary["total_distance_km"] == 300.0
    # 60% of 52 kWh over 300 km.
    assert summary["avg_efficiency_kwh_per_100km"] == pytest.approx(10.4)
    assert summary["energy_is_exact"] is True


def test_a_log_supplies_the_distance_and_the_price(client):
    """With receipts there is no need to guess either."""
    r = client.post("/api/v1/public/compare", json={
        "first": EV, "second": PETROL, "price_per_litre": 1.80,
        "events": [
            {"date": "2026-06-01", "odometer_km": 10_000, "energy_kwh": 40, "cost": 12.0},
            {"date": "2026-06-14", "odometer_km": 10_500, "energy_kwh": 50, "cost": 15.0},
        ],
    })

    assert r.status_code == 200
    body = r.json()
    assert body["distance_km"] == 500.0
    # 0.30 a kWh from the receipt, not the 0.28 nobody sent.
    assert body["actual_cost"] == pytest.approx(24.0)      # 80 kWh at 0.30


# --- limits -------------------------------------------------------------------

def test_a_comparison_with_nothing_to_measure_is_refused(client):
    r = client.post("/api/v1/public/compare", json={"first": EV, "second": PETROL})
    assert r.status_code == 422


def test_a_car_without_a_consumption_figure_is_refused_clearly(client):
    r = compare(client, EV, {"make": "Audi", "model": "A4", "fuel_type": "petrol"})
    assert r.status_code == 400
    assert "L/100km" in r.json()["detail"]


def test_a_visitor_cannot_send_an_unbounded_log(client):
    """Otherwise this is a way to make the server work for free."""
    events = [
        {"date": "2026-06-01", "odometer_km": i * 10, "energy_kwh": 10}
        for i in range(600)
    ]
    r = client.post("/api/v1/public/metrics", json={"vehicle": EV, "events": events})
    assert r.status_code == 422


def test_the_catalogue_is_readable_without_an_account(client, db):
    """Picking a car is the first thing a visitor does, so the list behind the
    dropdown has to be reachable too."""
    db.add(CatalogVehicle(id="x", source="evdb", make="Renault", model="4 E-Tech",
                          variant="4 E-Tech", fuel_type="electric"))
    db.commit()

    assert client.get("/api/v1/catalog/makes").status_code == 200
