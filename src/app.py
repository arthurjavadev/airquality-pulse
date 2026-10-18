"""AirQuality Pulse web UI, reporting API, health and HTTP metrics."""
from flask import Flask, Response, jsonify, render_template, request
from src.reporting import city_report, serialize_report
from src.collector import CITIES
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from src.monitoring import RequestMetrics

app = Flask(__name__)
_metrics = RequestMetrics(window_seconds=60)


@app.after_request
def record_request(response):
    # Do not count scrapes: they would distort the application request rate.
    if request.path not in ("/metrics", "/metrics/prometheus"):
        _metrics.record_request()
    return response


def validate_city(value):
    """Return a cleaned city name or an error message."""
    name = value.strip()
    if not name:
        return "", "Enter a city to continue."
    if len(name) > 80:
        return "", "City names must be 80 characters or fewer."
    return name, None


@app.route("/", methods=["GET", "POST"])
def index():
    city, error, submitted, report = "", None, False, None
    if request.method == "POST":
        city, error = validate_city(request.form.get("city", ""))
        submitted = error is None
        if submitted and city.casefold() in CITIES:
            try:
                report = city_report(city)
            except Exception:
                app.logger.exception("Failed to load air quality summary")
    return render_template("index.html", city=city, error=error,
                           submitted=submitted, report=report)


@app.get("/api/echo")
def echo():
    city, error = validate_city(request.args.get("city", ""))
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"city": city, "message": f"You searched for: {city}", "mode": "demo"})


@app.get("/api/air-quality")
def air_quality():
    city, error = validate_city(request.args.get("city", ""))
    if error:
        return jsonify({"error": error}), 400
    if city.casefold() not in CITIES:
        return jsonify({"error": "City is not supported"}), 400
    try:
        report = city_report(city)
    except Exception:
        app.logger.exception("Failed to query analysis database")
        return jsonify({"error": "Data is temporarily unavailable"}), 503
    if report is None:
        return jsonify({"error": "No analysis available yet for this city"}), 404
    return jsonify(serialize_report(report))


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/metrics")
def metrics():
    # Course rubric requires JSON and HTTP 200, rather than Prometheus text here.
    return jsonify(_metrics.snapshot()), 200


@app.get("/metrics/prometheus")
def prometheus_metrics():
    # Additional endpoint in the standard Prometheus exposition format.
    _metrics.snapshot()
    return Response(generate_latest(_metrics.registry), content_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    app.run(debug=False)
