# AirQuality Pulse — Web Application MVP

A deployable Flask web application for the Coursera *Applications of Software Architecture for Big Data* web-app assignment.

**What works now:** the user can enter a city name in a browser form, submit it to the Flask backend, and see the same city echoed on the page. A demo JSON API and a health endpoint are included.

**What is planned later:** real Open-Meteo air quality collection, a separate Data Collector, separate Data Analyzer, PostgreSQL storage, RabbitMQ events and monitoring. This milestone intentionally contains only the public-facing Web Application: it does **not** show real forecasts yet.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
python -m flask --app src.app run
```

Open <http://127.0.0.1:5000>, enter `Berlin`, press **Explore city**, and verify `You searched for: Berlin` appears. The app can also be tested with:

```bash
curl 'http://127.0.0.1:5000/api/echo?city=Berlin'
```

## Publish to GitHub

Create an empty GitHub repository named `airquality-pulse` (do not initialize it with README), then in this folder:

```bash
git init
git add .
git commit -m "Initial AirQuality Pulse web app"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/airquality-pulse.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your real GitHub username. You must authenticate when requested.

## Public deployment on Render (Free web service)

1. Go to <https://dashboard.render.com/>, click **New → Web Service**, and connect your GitHub repository.
2. Choose **Python 3** / **Python** runtime and **Free** plan if available.
3. Set **Build Command** to `pip install -r requirements.txt`.
4. Set **Start Command** to `gunicorn src.app:app`.
5. Set **Health Check Path** to `/health` (optional).
6. Click **Deploy Web Service** and wait for deployment to finish.
7. Open the actual `https://YOUR-ASSIGNED-NAME.onrender.com` link Render gives you. Enter a city and confirm your input is echoed.
8. Submit **that live URL**, not the GitHub repository URL, in the Coursera submission field.

The included `render.yaml` can alternatively be used for Render Blueprint deployment.

Render Free web services can spin down after periods of inactivity, so allow a short delay on the first request.

## Heroku alternative

A Heroku-compatible `Procfile` is included. Heroku hosting requires a paid dyno plan as of October 2026. Deploy using your Heroku account if you prefer that platform.

## App routes

- `GET /` — HTML form
- `POST /` — accept and echo city name
- `GET /api/echo?city=Berlin` — example JSON REST endpoint
- `GET /health` — simple health check
