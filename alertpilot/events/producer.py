from __future__ import annotations

import json
import logging

from .schemas import IncidentCreatedEvent

logger = logging.getLogger(__name__)


class KafkaIncidentProducer:
    def __init__(self, bootstrap_servers: str, topic: str, enabled: bool = False):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.enabled = enabled
        self._producer = None

    async def _ensure_started(self):
        if not self.enabled:
            return None
        if self._producer is not None:
            return self._producer
        try:
            from aiokafka import AIOKafkaProducer
        except Exception:
            logger.warning("aiokafka is not installed; incident events will not be published")
            self.enabled = False
            return None
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        )
        try:
            await self._producer.start()
        except Exception as exc:
            logger.warning("Kafka producer startup failed: %s", exc)
            self._producer = None
            self.enabled = False
            return None
        return self._producer

    async def publish_incident_created(self, event: IncidentCreatedEvent) -> bool:
        producer = await self._ensure_started()
        if producer is None:
            return False
        await producer.send_and_wait(self.topic, event.model_dump())
        return True

    async def close(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None
