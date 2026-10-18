"""Independent RabbitMQ Data Analyzer consumer process."""
from __future__ import annotations

import json
import logging
import time

from src.analyzer import analyze
from src.collector import CITIES
from src.messaging import ANALYSIS_QUEUE, EVENT_TYPE, broker_url, declare_topology

LOGGER = logging.getLogger(__name__)


def process_message(body: bytes, *, analyzer=analyze) -> dict:
    """Validate a collected-data event, then analyze committed SQL records."""
    event = json.loads(body)
    if not isinstance(event, dict) or event.get("version") != 1:
        raise ValueError("Unsupported event version")
    if event.get("type") != EVENT_TYPE:
        raise ValueError("Unsupported event type")
    city = event.get("city")
    if not isinstance(city, str) or city.casefold() not in CITIES:
        raise ValueError("Unsupported city in message")
    if not isinstance(event.get("event_id"), str) or not event["event_id"]:
        raise ValueError("Missing event ID")
    return analyzer(city)


def handle_delivery(channel, method, properties, body, *, analyzer=analyze) -> None:
    """Ack only after database analysis commits; dead-letter bad deliveries."""
    try:
        summary = process_message(body, analyzer=analyzer)
        LOGGER.info("Analysis saved for city=%s", summary["city"])
    except Exception:
        LOGGER.exception("Analysis failed; sending event to dead-letter queue")
        channel.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
    else:
        channel.basic_ack(delivery_tag=method.delivery_tag)


def consume_forever() -> None:
    import pika

    params = pika.URLParameters(broker_url())
    params.heartbeat = 60
    params.blocked_connection_timeout = 30
    connection = pika.BlockingConnection(params)
    try:
        channel = connection.channel()
        declare_topology(channel)
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue=ANALYSIS_QUEUE, on_message_callback=handle_delivery)
        LOGGER.info("Waiting for messages on queue %s", ANALYSIS_QUEUE)
        channel.start_consuming()
    finally:
        if connection.is_open:
            connection.close()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    broker_url()
    while True:
        try:
            consume_forever()
        except KeyboardInterrupt:
            return 0
        except Exception:
            LOGGER.exception("RabbitMQ connection failed; retry in 5 seconds")
            time.sleep(5)


if __name__ == "__main__":
    raise SystemExit(main())
