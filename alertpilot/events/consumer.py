from __future__ import annotations

import asyncio
import json
import logging

from alertpilot.config import Settings
from alertpilot.events.schemas import IncidentCreatedEvent

logger = logging.getLogger(__name__)


async def consume_incident_created(settings: Settings | None = None) -> None:
    settings = settings or Settings.from_env()
    try:
        from aiokafka import AIOKafkaConsumer
    except Exception as exc:
        raise RuntimeError("aiokafka is required to run the incident consumer") from exc

    consumer = AIOKafkaConsumer(
        settings.kafka_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_consumer_group,
        value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
    )
    await consumer.start()
    try:
        async for message in consumer:
            event = IncidentCreatedEvent(**message.value)
            logger.info(
                "notification_log incident_id=%s severity=%s service=%s owner_team=%s",
                event.incident_id,
                event.severity,
                event.service,
                event.owner_team,
            )
    finally:
        await consumer.stop()


if __name__ == "__main__":
    asyncio.run(consume_incident_created())
