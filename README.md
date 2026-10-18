# AirQuality Pulse - Final Course Project

Cloud-native air quality forecast collection, SQL analysis, asynchronous RabbitMQ messaging,
Flask reporting, monitoring, automated tests, and CI/CD.

This is the integrated course codebase for the Applications of Software Architecture for Big Data capstone.
It extends the previously submitted working Flask MVP without removing the city-echo feature.

## What is implemented

| Component | Implementation | Command |
| --- | --- | --- |
| Front end | Responsive HTML/CSS form and forecast summary | `gunicorn src.app:app` |
| Web API | `/api/echo`, `/api/air-quality`, `/health`, `/metrics`, `/metrics/prometheus` | `gunicorn src.app:app` |
| Data Collector | Open-Meteo HTTP GET, validation, SQL UPSERT | `python -m src.collector_worker` |
| Data Analyzer | SQL gateway, forecast statistics, persistent summaries | `python -m src.consumer` |
| Event collaboration | Pika, RabbitMQ direct exchange, durable queues, persistent events, ACK, DLQ | `python -m src.consumer` |
| Data persistence | SQLAlchemy with Alembic migrations, SQLite or PostgreSQL | `python -m src.migrate` |
| Observability | Prometheus Python Counter/Gauge, JSON metrics, health check | `/metrics` |
| Testing | Pure functions, fake REST API, broker test doubles, real SQLite integration | `python -m pytest -q` |
| CI and delivery | GitHub Actions test workflow; Render deploy after checks pass | `.github/workflows/ci.yml` |

## Event collaboration flow

1. Scheduler starts the independent collector worker.
2. Collector makes an HTTP GET request to Open-Meteo and saves forecast rows in SQL.
3. Only after successful SQL persistence, producer publishes a versioned `air_quality.collected` event to RabbitMQ.
4. RabbitMQ routes the persistent message to the durable `airquality.analysis` queue.
5. The independent consumer reads the message, queries SQL, calculates statistics and saves a summary.
6. Consumer sends RabbitMQ `basic_ack` only after the SQL analysis completes.
7. A failed message is rejected without requeueing and is sent to `airquality.analysis.dead` via the dead-letter exchange.
8. Flask reads the summary through a REST endpoint and shows it on the city page.

Events contain `event_id`, `version`, `type`, `city`, `record_count`, and `occurred_at_utc`.
They do not contain raw pollution values. This reduces broker message size and keeps SQL as the source of truth.
Duplicate deliveries are safe because summaries are UPSERTed by city. This course demonstration uses
at-least-once delivery semantics. For more rigorous guarantees, add a transactional outbox and
broker retries with delayed backoff; this demo does not claim to provide those guarantees.

### Sample message

```json
{
  "version": 1,
  "event_id": "f6ac1c0b-376f-4e78-83d7-e49c4b4ba074",
  "type": "air_quality.collected",
  "city": "Berlin",
  "record_count": 24,
  "occurred_at_utc": "2026-10-18T10:00:00+00:00"
}
```

### Local option A - Docker Compose (full architecture)

Requires Docker Engine + Docker Compose and network access for pulling images and collecting forecasts.

```bash
docker compose up --build -d
# The collector runs immediately, then once per hour.
docker compose logs -f collector analyzer
```

Visit:
- http://localhost:8000 - Flask dashboard
- http://localhost:8000/health - health check, HTTP 200
- http://localhost:8000/metrics - JSON request rate
- http://localhost:8000/metrics/prometheus - Prometheus text
- http://localhost:8000/api/air-quality?city=Berlin - SQL-backed report, once collected
- http://localhost:15672 - RabbitMQ dashboard, user `airquality`, password `local_dev_only`

For one extra collection:

```bash
docker compose run --rm collector python -m src.collector_worker --cities Berlin
```

Stop the containers without deleting the data:

```bash
docker compose down
```

`docker compose down -v` also **deletes local database and RabbitMQ volumes**, so do not use `-v`
unless you intentionally want to remove all saved local data.

The sample compose credentials are **local development only**. Never copy them to a public server.

### Local option B - Python with SQLite (without Docker)

Requires Python 3.12 or newer and pip.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m src.migrate
python -m src.collector --city Berlin
python -m src.analyzer --city Berlin
python -m src.show_analysis --city Berlin
python -m pytest -q
flask --app src.app run
```

This standalone route runs the collector and analyzer separately but does not exercise RabbitMQ.
To exercise messaging, start RabbitMQ and set `RABBITMQ_URL` and then run:

```bash
python -m src.consumer
# In another terminal, after migrations:
python -m src.collector_worker --cities Berlin
```

### Database configuration

Without `DATABASE_URL`, the program uses local SQLite file `./airquality.db`.
For all services in the same deployment, set `DATABASE_URL` to the same PostgreSQL connection URI.
For messaging, set `RABBITMQ_URL` on the collector and analyzer only.

Never commit production credentials or a `.env` file to GitHub.
Database migrations (including both forecast and summary tables) are in `migrations/versions`.

## Deploying to Render and GitHub

See [DEPLOY_RU.md](DEPLOY_RU.md) for the precise, safe deployment procedure.

**Important:** A free Render web service can run the HTTP app, but it cannot host the continuously
running independent analyzer and collector workers. Free web service storage is ephemeral.
Full cloud operation requires a persistent shared database, RabbitMQ broker, and a supported
worker/cron hosting arrangement. Docker Compose provides a full runnable local deployment.

The `render.yaml` included here configures ONLY a free web service, without creating new paid services.
Using this file does not automatically modify the existing web service. Existing deployments
remain unchanged until this repository is updated and Render redeploys successfully.

## Quality, scope, and known limitations

- API source: https://open-meteo.com/en/docs/air-quality-api
- Open-Meteo supplies model forecasts, not direct historical sensor measurements.
- The pipeline currently supports Berlin, Frankfurt, London and Paris with fixed coordinates.
- Data quality checks validate field presence, array lengths and UTC hourly timestamps.
- Data Collector UPSERT makes repeated ingestion idempotent per city and forecast hour.
- A missing metric is excluded from averages rather than replaced by zero.
- Trends represent first-to-last forecast changes, not historical observation trends.
- `/health` checks HTTP process liveness, not external service connectivity.
- HTTP counters are per process and reset on restart. One Gunicorn worker is configured.
- A permanently failing event is sent to the DLQ; human intervention may be needed to replay it.
- A crash after DB commit and before publish can lose a notification. Transactional outbox is future work.
- Full live RabbitMQ and Open-Meteo cloud checks must be done in a networked runtime.

## Project layout

```text
src/
  app.py               Web UI, REST API, metrics and health
  collector.py         External REST API + SQL persistence
  collector_worker.py  Scheduled producer + event publisher
  consumer.py          RabbitMQ listener + analysis ACK/DLQ
  analyzer.py          Forecast statistics + SQL persistence
  messaging.py         Durable exchange/queue and event publisher
  monitoring.py        Request counters and rate gauge
  reporting.py         SQL-backed reports for web users
  data/                SQL models and database gateways
migrations/versions/   Alembic schema migrations
.github/workflows/     Tests on every main branch push
compose.yaml           Local Postgres + RabbitMQ + 3 independent apps
Dockerfile             Shared container image
render.yaml            Safe web-only Render definition
ARCHITECTURE.puml      Editable architecture diagram
DEPLOY_RU.md           Deployment instructions in Russian
tests/                 Unit tests, integration tests and mocks
```
