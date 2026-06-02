import asyncio
import sys
import types

from alertpilot.events.producer import KafkaIncidentProducer
from alertpilot.events.schemas import IncidentCreatedEvent


def run(coro):
    return asyncio.run(coro)


def make_event():
    return IncidentCreatedEvent(
        incident_id="incident-1",
        fingerprint="fp",
        title="checkout outage",
        service="checkout-api",
        environment="prod",
        severity="critical",
        owner_team="payments-platform",
        runbook_url="https://runbooks.local/checkout-api",
        source="prometheus",
        occurrence_count=1,
    )


def test_kafka_producer_disabled_returns_false():
    producer = KafkaIncidentProducer("localhost:9092", "incident.created", enabled=False)
    assert run(producer.publish_incident_created(make_event())) is False
    run(producer.close())


def test_kafka_producer_handles_missing_aiokafka(monkeypatch):
    monkeypatch.setitem(sys.modules, "aiokafka", None)
    producer = KafkaIncidentProducer("localhost:9092", "incident.created", enabled=True)
    assert run(producer.publish_incident_created(make_event())) is False
    assert producer.enabled is False


def test_kafka_producer_sends_event_with_fake_aiokafka(monkeypatch):
    sent = []

    class FakeProducer:
        def __init__(self, bootstrap_servers, value_serializer):
            self.bootstrap_servers = bootstrap_servers
            self.value_serializer = value_serializer
            self.started = False
            self.stopped = False

        async def start(self):
            self.started = True

        async def send_and_wait(self, topic, value):
            sent.append((topic, value))
            assert self.value_serializer(value)

        async def stop(self):
            self.stopped = True

    fake_module = types.SimpleNamespace(AIOKafkaProducer=FakeProducer)
    monkeypatch.setitem(sys.modules, "aiokafka", fake_module)

    producer = KafkaIncidentProducer("kafka:9092", "incident.created", enabled=True)
    assert run(producer.publish_incident_created(make_event())) is True
    assert sent[0][0] == "incident.created"
    assert sent[0][1]["severity"] == "critical"
    run(producer.close())
    assert producer._producer is None


def test_kafka_producer_disables_on_start_failure(monkeypatch):
    class BrokenProducer:
        def __init__(self, *args, **kwargs):
            pass

        async def start(self):
            raise RuntimeError("kafka unavailable")

    fake_module = types.SimpleNamespace(AIOKafkaProducer=BrokenProducer)
    monkeypatch.setitem(sys.modules, "aiokafka", fake_module)

    producer = KafkaIncidentProducer("kafka:9092", "incident.created", enabled=True)
    assert run(producer.publish_incident_created(make_event())) is False
    assert producer.enabled is False
