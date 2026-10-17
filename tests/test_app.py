import pytest
from src.app import app


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def test_homepage_has_city_form(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b'name="city"' in res.data
    assert b"AirQuality Pulse" in res.data


def test_user_input_is_echoed_on_page(client):
    res = client.post("/", data={"city": "Frankfurt"})
    assert res.status_code == 200
    assert b"You searched for: Frankfurt" in res.data


def test_empty_input_is_rejected(client):
    res = client.post("/", data={"city": "   "})
    assert res.status_code == 200
    assert b"Enter a city to continue" in res.data


def test_html_injection_is_escaped(client):
    res = client.post("/", data={"city": "<script>alert(1)</script>"})
    assert b"&lt;script&gt;" in res.data
    assert b"<script>alert(1)</script>" not in res.data


def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json == {"status": "ok"}


def test_api_echo(client):
    res = client.get("/api/echo?city=Berlin")
    assert res.status_code == 200
    assert res.json["city"] == "Berlin"
    assert res.json["mode"] == "demo"


def test_api_echo_requires_city(client):
    res = client.get("/api/echo")
    assert res.status_code == 400
    assert "error" in res.json
