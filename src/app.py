"""Minimal AirQuality Pulse web app for the Coursera Web Application assignment.

This initial MVP intentionally echoes a city name. It does not yet fetch
or analyze live air-quality data. Collector and analyzer are future modules.
"""
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)


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
    city, error, submitted = "", None, False
    if request.method == "POST":
        city, error = validate_city(request.form.get("city", ""))
        submitted = error is None
    return render_template("index.html", city=city, error=error, submitted=submitted)


@app.get("/api/echo")
def echo():
    city, error = validate_city(request.args.get("city", ""))
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"city": city, "message": f"You searched for: {city}", "mode": "demo"})


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=False)
