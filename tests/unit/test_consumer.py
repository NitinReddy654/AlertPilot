import asyncio
import sys

import pytest

from alertpilot.events.consumer import consume_incident_created


def test_consumer_requires_aiokafka(monkeypatch):
    monkeypatch.setitem(sys.modules, "aiokafka", None)
    with pytest.raises(RuntimeError):
        asyncio.run(consume_incident_created())


def test_consumer_reads_incident_event(monkeypatch):
    import types

    class Message:
        value = {
            "event_type": "incident.created",
            "incident_id": "incident-1",
            "fingerprint": "fp",
            "title": "checkout outage",
            "service": "checkout-api",
            "environment": "prod",
            "severity": "critical",
            "owner_team": "payments-platform",
            "runbook_url": "https://runbooks.local/checkout-api",
            "source": "prometheus",
            "occurrence_count": 1,
        }

    class FakeConsumer:
        def __init__(self, *args, **kwargs):
            self.index = 0
            self.started = False
            self.stopped = False

        async def start(self):
            self.started = True

        async def stop(self):
            self.stopped = True

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.index == 0:
                self.index += 1
                return Message()
            raise StopAsyncIteration

    monkeypatch.setitem(sys.modules, "aiokafka", types.SimpleNamespace(AIOKafkaConsumer=FakeConsumer))
    asyncio.run(consume_incident_created())
