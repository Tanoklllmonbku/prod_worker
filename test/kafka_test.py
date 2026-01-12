import asyncio

from core.factories import _create_queue_connector
from config.config import get_settings
import unittest


class TestKafkaConnector(unittest.IsolatedAsyncioTestCase):
    """
    Unit-тесты для KafkaConnector, использующие фабрику и переменные окружения.
    Использует IsolatedAsyncioTestCase для корректной работы с async/await.
    Предполагает, что Kafka-брокер запущен на localhost:9092 (из .env).
    """

    @classmethod
    def setUpClass(cls):
        """
        Выполняется один раз перед всеми тестами в классе.
        Подготавливает настройки и создаёт коннектор.
        """
        # Убедимся, что используем переменные окружения
        cls.config = get_settings()
        cls.bootstrap_servers = cls.config.kafka.bootstrap_servers
        print(f"Using Kafka servers: {cls.bootstrap_servers}")

        # Создаём коннектор через фабрику
        cls.connector = _create_queue_connector(cls.config)

    async def asyncSetUp(self):
        """
        Асинхронная инициализация коннектора перед каждым тестом.
        """
        print("Initializing Kafka connector...")
        await self.connector.initialize()
        print("Kafka connector initialized.")

    async def asyncTearDown(self):
        """
        Асинхронная очистка после каждого теста.
        """
        print("Shutting down Kafka connector...")
        await self.connector.shutdown()
        print("Kafka connector shut down.")

    async def test_initialization(self):
        """
        Тест: Коннектор успешно инициализируется.
        """
        # asyncSetUp уже вызван автоматически
        # Проверим, что _producer не None после инициализации
        self.assertIsNotNone(self.connector._producer)
        print("Initialization test passed.")

    async def test_health_check(self):
        """
        Тест: Проверка состояния коннектора.
        """
        # asyncSetUp уже вызван автоматически
        is_healthy = await self.connector.health_check()
        self.assertTrue(is_healthy, "Kafka connector should be healthy if Kafka is running.")
        print("Health check test passed.")

    async def test_publish_and_consume(self):
        """
        Тест: Публикация сообщения и его получение.
        """
        topic = "test-topic"  # Убедитесь, что топик существует в Kafka
        group_id = "test-consumer-group"
        test_message_data = {"key1": "value1", "key2": 123}

        # asyncSetUp уже вызван автоматически

        # 1. Подписываемся на топик
        await self.connector.subscribe(
            topics=[topic],
            group_id=group_id,
        )
        await asyncio.sleep(1)  # Даём время consumer-потоку запуститься

        # 2. Публикуем сообщение
        datagram_id = "test_datagram_123"
        await self.connector.publish(
            topic=topic,
            datagram_id=datagram_id,
            data=test_message_data,
        )
        print(f"Published message to {topic}")

        # 3. Потребляем сообщение
        # consume возвращает Dict, как в обновлённой версии
        consumed_message = await asyncio.wait_for(self.connector.consume(), timeout=10.0)
        print(f"Consumed raw message: {consumed_message}")

        # 4. Проверяем содержимое
        # В обновлённой версии consume возвращает {"payload": {...}, ...}
        payload = consumed_message.get("payload", {})
        self.assertEqual(payload, test_message_data)

        print("Publish and consume test passed.")