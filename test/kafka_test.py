import asyncio
import logging
from connectors import KafkaConnector, SerializationFormat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    kc = KafkaConnector(
        bootstrap_servers=["localhost:9092"],
        logger=logger,
        default_format=SerializationFormat.JSON,
    )

    await kc.initialize()

    # Запустить consumer
    await kc.subscribe(
        topics=["gigachat.requests"],
        group_id="test-group",
        format_type=SerializationFormat.JSON,
    )

    # Паблиш
    await kc.publish(
        topic="gigachat.requests",
        datagram_id="gigachat.ChatRequest",
        data={"prompt": "Hello", "temperature": 0.1},
        key="user-1",
    )

    # Асинхронно прочитать
    envelope = await kc.consume()
    print("Got:", envelope)

    await kc.shutdown()


asyncio.run(main())
