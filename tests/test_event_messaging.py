"""Event messaging tests: broker fakes plus real SQL-backed integration."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from src.collector import collect
from src.collector_worker import collect_and_publish
from src.consumer import handle_delivery, process_message
from src.data.analysis_gateway import AnalysisGateway
from src.data.database import make_engine
from src.data.gateway import ForecastGateway
from src.messaging import (
    ANALYSIS_QUEUE, DEAD_QUEUE, EXCHANGE, ROUTING_KEY,
    collected_event, declare_topology, publish_event,
)
from src.migrate import upgrade_database


class MockChannel:
    def __init__(self):
        self.exchanges, self.queues, self.bindings = [], [], []
        self.published, self.acked, self.rejected = [], [], []
        self.confirmed = False

    def exchange_declare(self, **kw):
        self.exchanges.append(kw)

    def queue_declare(self, **kw):
        self.queues.append(kw)

    def queue_bind(self, **kw):
        self.bindings.append(kw)

    def confirm_delivery(self):
        self.confirmed = True

    def basic_publish(self, **kw):
        self.published.append(kw)

    def basic_ack(self, *, delivery_tag):
        self.acked.append(delivery_tag)

    def basic_reject(self, *, delivery_tag, requeue):
        self.rejected.append((delivery_tag, requeue))


class MockConnection:
    def __init__(self, ch):
        self.ch, self.is_open = ch, True

    def channel(self):
        return self.ch

    def close(self):
        self.is_open = False


class MockHttp:
    def __init__(self, payload):
        self.payload = payload

    def get(self, url, *, params, timeout):
        return SimpleNamespace(raise_for_status=lambda: None,
                               json=lambda: self.payload)


@pytest.fixture
def db_url(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'event_integration.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    upgrade_database()
    return url


def test_topology_declares_durable_queue_with_dlq():
    ch = MockChannel()
    declare_topology(ch)
    assert {q["queue"] for q in ch.queues} == {ANALYSIS_QUEUE, DEAD_QUEUE}
    assert all(q["durable"] for q in ch.queues)
    assert any(q["queue"] == ANALYSIS_QUEUE and
               q["arguments"]["x-dead-letter-exchange"] for q in ch.queues)
    assert {e["exchange"] for e in ch.exchanges} == {EXCHANGE, "airquality.dead"}


def test_event_published_as_persistent_json_with_confirm(monkeypatch):
    monkeypatch.setenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F")
    ch = MockChannel()
    conn = MockConnection(ch)
    event = collected_event("Berlin", 24)
    fake_pika = SimpleNamespace(
        URLParameters=lambda url: SimpleNamespace(url=url),
        BasicProperties=lambda **kw: SimpleNamespace(**kw),
    )
    publish_event(event, connection_factory=lambda params: conn, pika_module=fake_pika)
    assert ch.confirmed and len(ch.published) == 1
    msg = ch.published[0]
    assert msg["mandatory"] is True
    assert msg["exchange"] == EXCHANGE and msg["routing_key"] == ROUTING_KEY
    assert msg["properties"].delivery_mode == 2
    assert json.loads(msg["body"])["city"] == "Berlin"
    assert not conn.is_open


def test_consumer_acks_after_success():
    ch, method = MockChannel(), SimpleNamespace(delivery_tag=11)
    event = collected_event("Berlin", 3)
    handle_delivery(ch, method, None, json.dumps(event).encode(),
                    analyzer=lambda city: {"city": city})
    assert ch.acked == [11] and ch.rejected == []


def test_consumer_dead_letters_failed_message():
    ch, method = MockChannel(), SimpleNamespace(delivery_tag=7)
    handle_delivery(ch, method, None, b"not json")
    assert ch.rejected == [(7, False)] and not ch.acked
    ch2 = MockChannel()
    event = collected_event("Berlin", 3)

    def broken_analyzer(city):
        raise ConnectionError("database unavailable")

    handle_delivery(ch2, method, None, json.dumps(event).encode(),
                    analyzer=broken_analyzer)
    assert ch2.rejected == [(7, False)]


def test_invalid_city_does_not_run_analyzer():
    event = collected_event("Unsupported", 4)
    with pytest.raises(ValueError, match="Unsupported city"):
        process_message(json.dumps(event).encode(),
                        analyzer=lambda _: pytest.fail("unexpected"))


def test_integration_collect_publish_consume_and_save_sql(db_url):
    """Real SQLite, mocked HTTP and in-memory broker for complete data flow."""
    fixture = Path(__file__).parent / "fixtures" / "open_meteo_sample.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    channel = MockChannel()

    def real_sql_collection(city):
        return collect(city, http_client=MockHttp(payload), database_url=db_url)

    def fake_publish(city, count):
        event = collected_event(city, count)
        channel.basic_publish(exchange=EXCHANGE, routing_key=ROUTING_KEY,
                              body=json.dumps(event).encode())
        return event

    done, failed = collect_and_publish(["Berlin"], collect_fn=real_sql_collection,
                                       publish_fn=fake_publish)
    assert failed == [] and done[0]["record_count"] == 3
    engine = make_engine(db_url)
    try:
        assert ForecastGateway(engine).count() == 3
    finally:
        engine.dispose()

    from src.analyzer import analyze
    method = SimpleNamespace(delivery_tag=21)
    handle_delivery(channel, method, None, channel.published[0]["body"],
                    analyzer=lambda city: analyze(city, database_url=db_url))
    assert channel.acked == [21]
    engine = make_engine(db_url)
    try:
        report = AnalysisGateway(engine).find_by_city("Berlin")
        assert report["forecast_hours"] == 3
        assert report["max_european_aqi"] == 32
        assert report["mean_pm2_5"] == 7.43
    finally:
        engine.dispose()
