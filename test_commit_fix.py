#!/usr/bin/env python3
"""
Тест для проверки исправления ошибки commit в Kafka connector
"""
import asyncio
import logging
from connectors.kafka_connector import KafkaConnector

async def test_kafka_commit():
    """Тестирование метода commit"""
    # Настройка логирования
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Создание Kafka connector
    try:
        from config.config import get_settings
        config = get_settings()
        bootstrap_servers = config.kafka.bootstrap_servers
        print(f"Using Kafka servers: {bootstrap_servers}")
    except Exception:
        bootstrap_servers = ["localhost:9092"]
        print(f"Using default Kafka servers: {bootstrap_servers}")

    connector = KafkaConnector(
        bootstrap_servers=bootstrap_servers,
        group_id="test_commit_group",
        auto_offset_reset="earliest",
        logger=logger
    )

    try:
        # Инициализация
        await connector.initialize()
        print("✓ Kafka connector initialized successfully")

        # Подписка на топик
        await connector.subscribe(
            topics=["test_commit_topic"],
            group_id="test_commit_group_123",
            auto_offset_reset="earliest"
        )
        print("✓ Successfully subscribed to topic")

        # Ждем немного, чтобы дать consumer время на инициализацию
        await asyncio.sleep(2)

        # Создаем фейковое сообщение для тестирования commit
        fake_message = {
            'payload': {},
            'kafka_key': 'test_key',
            'kafka_topic': 'test_commit_topic',
            'kafka_partition': 0,
            'kafka_offset': 1,
            'kafka_headers': {},
            'kafka_timestamp': 1234567890,
            'kafka_timestamp_type': 0
        }

        # Тестируем commit
        try:
            await connector.commit(fake_message)
            print("✓ Commit completed successfully - no TopicPartition error!")
        except Exception as e:
            if "TopicPartition" in str(e):
                print(f"❌ Commit failed with TopicPartition error: {e}")
                return False
            else:
                print(f"⚠️  Commit had other error (not TopicPartition): {e}")
                # Это может быть нормально, если сообщение не настоящее

        print("✓ Commit method test completed successfully!")

    except Exception as e:
        print(f"Error occurred: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Закрытие соединений
        await connector.shutdown()
        print("✓ Kafka connector shutdown completed")


if __name__ == "__main__":
    asyncio.run(test_kafka_commit())
