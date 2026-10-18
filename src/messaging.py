"""RabbitMQ event collaboration for separate data collection and analysis apps.

All messages contain non-sensitive metadata. Forecast values stay in SQL.
The broker transports instructions, not database records.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import uuid

EXCHANGE = "airquality.events"
ROUTING_KEY = "forecast.collected"
ANALYSIS_QUEUE = "airquality.analysis"
DEAD_EXCHANGE = "airquality.dead"
DEAD_QUEUE = "airquality.analysis.dead"
EVENT_TYPE = "air_quality.collected"


def declare_topology(channel) -> None:
    """Declare a durable queue, event exchange, and dead-letter routing."""
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="direct", durable=True)
    channel.exchange_declare(exchange=DEAD_EXCHANGE, exchange_type="direct", durable=True)
    channel.queue_declare(queue=DEAD_QUEUE, durable=True)
    channel.queue_bind(queue=DEAD_QUEUE, exchange=DEAD_EXCHANGE, routing_key="failed")
    channel.queue_declare(
        queue=ANALYSIS_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": DEAD_EXCHANGE,
            "x-dead-letter-routing-key": "failed",
        },
    )
    channel.queue_bind(queue=ANALYSIS_QUEUE, exchange=EXCHANGE, routing_key=ROUTING_KEY)


def collected_event(city: str, record_count: int) -> dict:
    """Build a small, versioned event after rows are committed to the SQL DB."""
    if not city or record_count < 1:
        raise ValueError("City and a positive record count are required")
    return {
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "type": EVENT_TYPE,
        "city": city,
        "record_count": record_count,
        "occurred_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def broker_url() -> str:
    url = os.environ.get("RABBITMQ_URL", "").strip()
    if not url:
        raise RuntimeError("Set RABBITMQ_URL before publishing or consuming events")
    if not (url.startswith("amqp://") or url.startswith("amqps://")):
        raise ValueError("RABBITMQ_URL must start with amqp:// or amqps://")
    return url


def publish_event(event: dict, *, connection_factory=None, pika_module=None) -> None:
    """Publish a persistent message and wait for broker confirmation.

    Caller must persist database records BEFORE publishing the event.
    Message publishing is at-least-once, so analysis must be idempotent.
    """
    if pika_module is None:
        import pika as pika_module
    if connection_factory is None:
        connection_factory = pika_module.BlockingConnection

    params = pika_module.URLParameters(broker_url())
    params.heartbeat = 60
    params.blocked_connection_timeout = 30
    connection = connection_factory(params)
    try:
        channel = connection.channel()
        declare_topology(channel)
        channel.confirm_delivery()
        channel.basic_publish(
            exchange=EXCHANGE,
            routing_key=ROUTING_KEY,
            body=json.dumps(event).encode("utf-8"),
            mandatory=True,
            properties=pika_module.BasicProperties(
                delivery_mode=2, content_type="application/json",
                message_id=event["event_id"], type=event["type"],
            ),
        )
    finally:
        if connection.is_open:
            connection.close()


def publish_collected_event(city: str, record_count: int, **kwargs) -> dict:
    event = collected_event(city, record_count)
    publish_event(event, **kwargs)
    return event
