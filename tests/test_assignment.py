"""AirQuality Pulse: unit and integration tests for the course assignment."""

from src.app import app, validate_city


def test_validate_city_trims_whitespace():
    """Unit test: input validation cleans a city name without an HTTP request."""
    city, error = validate_city("  Berlin  ")
    assert city == "Berlin"
    assert error is None


def test_city_form_submission():
    """Integration test: HTTP form -> Flask handler -> rendered HTML."""
    app.config.update(TESTING=True)
    with app.test_client() as client:
        response = client.post("/", data={"city": "Berlin"})

    assert response.status_code == 200
    assert b"You searched for: Berlin" in response.data
