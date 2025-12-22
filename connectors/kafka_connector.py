import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from threading import Thread, Event
from typing import Any, Dict, List, Optional

from kafka import KafkaProducer, KafkaConsumer

from core.base_class.connectors import QueueConnector


class SerializationFormat(str, Enum):
    JSON = "json"
    MSGPACK = "msgpack"


class Serializer:
    def __init__(self, fmt: SerializationFormat):
        self.fmt = fmt

    def serialize(self, data: Dict[str, Any]) -> bytes:
        if self.fmt == SerializationFormat.JSON:
            return json.dumps(data).encode("utf-8")
        elif self.fmt == SerializationFormat.MSGPACK:
            try:
                import msgspec
            except ImportError:
                raise ImportError("msgspec required for msgpack: pip install msgspec")
            return msgspec.json.encode(data)
        else:
            raise ValueError(f"Unsupported format: {self.fmt}")

    def deserialize(self, data: bytes) -> Dict[str, Any]:
        if self.fmt == SerializationFormat.JSON:
            return json.loads(data.decode("utf-8"))
        elif self.fmt == SerializationFormat.MSGPACK:
            try:
                import msgspec
            except ImportError:
                raise ImportError("msgspec required for msgpack: pip install msgspec")
            return msgspec.json.decode(data)
        else:
            raise ValueError(f"Unsupported format: {self.fmt}")


@dataclass
class DatagramEnvelope:
    datagram_id: str
    data: Dict[str, Any]
    format: str
    timestamp: str
    key: Optional[str] = None
    partition: Optional[int] = None
    offset: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "datagram_id": self.datagram_id,
            "data": self.data,
            "format": self.format,
            "timestamp": self.timestamp,
            "key": self.key,
            "partition": self.partition,
            "offset": self.offset,
        }


class KafkaConnector(QueueConnector):
    """
    Asyncio-friendly Kafka connector on top of kafka-python.
    Thread-safe:
      - Producer: используется из event loop (по сути один поток).
      - Consumer: отдельный поток, сообщения прокидываются в asyncio.Queue.
    """

    def __init__(
        self,
        bootstrap_servers: List[str],
        logger: Optional[logging.Logger] = None,
        default_format: SerializationFormat = SerializationFormat.JSON,
        consumer_poll_timeout: float = 1.0,
    ) -> None:
        super().__init__(name="kafka")
        self.bootstrap_servers = bootstrap_servers
        self.logger = logger or logging.getLogger(__name__)
        self.default_format = default_format
        self.consumer_poll_timeout = consumer_poll_timeout

        self._producer: Optional[KafkaProducer] = None

        # consumer управляется отдельным потоком
        self._consumer_thread: Optional[Thread] = None
        self._consumer_stop_event = Event()
        self._consumer: Optional[KafkaConsumer] = None

        # Очередь сообщений для asyncio-части
        self._message_queue: asyncio.Queue[DatagramEnvelope] = asyncio.Queue()

        # Флаг и топики для подписки
        self._subscribed_topics: List[str] = []
        self._group_id: Optional[str] = None
        self._consumer_running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ----------------- Инициализация / shutdown -----------------

    async def initialize(self) -> None:
        """Создать KafkaProducer (в event loop, но он блокирующий внутри)."""
        loop = asyncio.get_running_loop()
        self._loop = asyncio.get_running_loop()
        def _create_producer() -> KafkaProducer:
            return KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: v,  # уже bytes
                key_serializer=lambda k: k.encode("utf-8") if k is not None else None,
            )

        self._producer = await loop.run_in_executor(None, _create_producer)
        self.logger.info("Kafka producer initialized")

    async def shutdown(self) -> None:
        """Остановить producer и consumer-поток."""
        # Остановка consumer
        if self._consumer_running:
            self._consumer_stop_event.set()
            if self._consumer_thread:
                self._consumer_thread.join(timeout=5)
            self._consumer_running = False
            self.logger.info("Kafka consumer thread stopped")

        # Закрыть producer
        if self._producer is not None:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._producer.flush)
            await loop.run_in_executor(None, self._producer.close)
            self.logger.info("Kafka producer closed")

    # ----------------- Публикация -----------------

    async def publish(
        self,
        topic: str,
        datagram_id: str,
        data: Dict[str, Any],
        format_type: Optional[SerializationFormat] = None,
        key: Optional[str] = None,
        **_: Any,
    ) -> None:
        """
        Асинхронная публикация сообщения.
        """
        if self._producer is None:
            raise RuntimeError("Kafka producer not initialized")

        fmt = format_type or self.default_format
        serializer = Serializer(fmt)

        envelope = {
            "datagram_id": datagram_id,
            "data": data,
            "format": fmt.value,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        payload = serializer.serialize(envelope)

        loop = asyncio.get_running_loop()

        def _send() -> None:
            assert self._producer is not None
            fut = self._producer.send(topic, value=payload, key=key)
            # Можно повесить callback при желании
            try:
                fut.get(timeout=10)
            except Exception as e:
                self.logger.error(f"Error sending to Kafka: {e}", exc_info=True)
                raise

        await loop.run_in_executor(None, _send)

    async def batch_publish(
        self,
        topic: str,
        messages: List[tuple],  # (datagram_id, data, key, format_type?)
        default_format: Optional[SerializationFormat] = None,
        **_: Any,
    ) -> None:
        """
        Батч-отправка. format_type можно прокинуть в каждом сообщении, если нужно.
        """
        if self._producer is None:
            raise RuntimeError("Kafka producer not initialized")

        loop = asyncio.get_running_loop()

        def _send_batch() -> None:
            for item in messages:
                if len(item) == 4:
                    datagram_id, data, key, fmt = item
                    fmt = fmt or default_format or self.default_format
                else:
                    datagram_id, data, key = item
                    fmt = default_format or self.default_format

                serializer = Serializer(fmt)
                envelope = {
                    "datagram_id": datagram_id,
                    "data": data,
                    "format": fmt.value,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
                payload = serializer.serialize(envelope)

                assert self._producer is not None
                fut = self._producer.send(topic, value=payload, key=key)
                fut.get(timeout=10)
            self._producer.flush()

        await loop.run_in_executor(None, _send_batch)

    # ----------------- Подписка / Consumer -----------------

    async def subscribe(
        self,
        topics: List[str],
        group_id: str,
        format_type: Optional[SerializationFormat] = None,
        auto_offset_reset: str = "earliest",
        **_: Any,
    ) -> None:
        """
        Запустить consumer в отдельном потоке.
        Сообщения будут приходить в self._message_queue.
        """
        if self._consumer_running:
            raise RuntimeError("Consumer already running")

        self._subscribed_topics = topics
        self._group_id = group_id

        fmt = format_type or self.default_format
        serializer = Serializer(fmt)

        def _consumer_loop() -> None:
            self.logger.info(f"Kafka consumer thread started: topics={topics}, group={group_id}")
            consumer = KafkaConsumer(
                *topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id=group_id,
                auto_offset_reset=auto_offset_reset,
                enable_auto_commit=True,
                value_deserializer=lambda v: v,  # bytes
                key_deserializer=lambda k: k.decode("utf-8") if k is not None else None,
            )
            self._consumer = consumer

            try:
                while not self._consumer_stop_event.is_set():
                    records = consumer.poll(timeout_ms=int(self.consumer_poll_timeout * 1000))
                    for tp, batch in records.items():
                        for msg in batch:
                            try:
                                env_dict = serializer.deserialize(msg.value)
                                envelope = DatagramEnvelope(
                                    datagram_id=env_dict.get("datagram_id", ""),
                                    data=env_dict.get("data", {}),
                                    format=env_dict.get("format", fmt.value),
                                    timestamp=env_dict.get("timestamp", ""),
                                    key=msg.key,
                                    partition=msg.partition,
                                    offset=msg.offset,
                                )
                                asyncio.run_coroutine_threadsafe(
                                    self._message_queue.put(envelope),
                                    self._loop,  # ← тут
                                )
                            except Exception as e:
                                self.logger.error(f"Error decoding message: {e}", exc_info=True)
            finally:
                consumer.close()

        # Поднимаем поток
        self._consumer_stop_event.clear()
        self._consumer_running = True
        self._consumer_thread = Thread(target=_consumer_loop, daemon=True)
        self._consumer_thread.start()

    async def consume(self) -> DatagramEnvelope:
        """
        Асинхронно получить следующее сообщение (из очереди).
        Блокирует до появления сообщения.
        """
        envelope = await self._message_queue.get()
        return envelope

    async def health_check(self) -> bool:
        """
        Простейшая проверка доступности брокера:
        - продюсер должен быть инициализирован
        - пытаемся получить метаданные по топикам (если уже есть подписка)
        """
        try:
            if not self._producer:
                return False

            # Лёгкая проверка: запрос метаданных
            future = self._producer.send("health-check-topic", b"ping")
            future.get(timeout=5)
            self._set_health(True)
            return True
        except Exception as exc:
            self.logger.warning(f"Kafka health check failed: {exc}")
            self._set_health(False)
            return False
