"""
Queue Interface - Strategy pattern implementation for message queue connectors.

Allows switching between different queue providers (Kafka, RabbitMQ, Redis, etc.)
while maintaining the same API.
"""

import uuid
from typing import Any, Dict, List, Optional

from core.base_class.base_interface import BaseInterface
from core.base_class.protocols import IQueueConnector
from utils.observer import EventPublisher
from core.registry import register_interface


@register_interface("Kafka")
class QueueInterface(BaseInterface):
    """
    High-level interface for message queue operations.

    Implements Strategy pattern - can switch between different queue providers
    (Kafka, RabbitMQ, Redis, etc.) transparently.
    """

    def __init__(
        self,
        worker: IQueueConnector,
        name: Optional[str] = None,
        event_publisher: Optional[EventPublisher] = None,
    ) -> None:
        """
        Initialize Queue interface.

        Args:
            worker: Queue connector instance (e.g., KafkaConnector)
            name: Interface name (defaults to worker name)
            event_publisher: Optional event publisher for observability
        """
        super().__init__(worker, name, event_publisher)

    @property
    def worker(self) -> IQueueConnector:
        """Get underlying queue connector"""
        return self._worker

    async def publish(
        self,
        topic: str,
        key: Optional[str] = None,
        headers: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        """
        Publish message to queue (совместимо с documents_service).
        """
        # Подготовим сообщение для worker
        message_data = data or {}

        # Используем key как datagram_id
        datagram_id = key or str(uuid.uuid4())

        await self._execute_with_tracking(
            "publish",
            self._worker.publish,
            topic,
            datagram_id,
            message_data,
            key=key,
            headers=headers,
            **kwargs,
            metadata={"topic": topic, "key": key},
        )

    async def commit(self, message: Dict[str, Any]) -> None:
        """Commit consumed message"""
        if hasattr(self._worker, "commit"):
            await self._execute_with_tracking(
                "commit",
                self._worker.commit,
                message,
                metadata={
                    "consumer_group": getattr(self._worker, "group_id", "unknown")
                },
            )

    async def batch_publish(
        self,
        topic: str,
        messages: List[Any],
        **kwargs: Any,
    ) -> None:
        """
        Publish batch of messages.

        Args:
            topic: Topic/queue name
            messages: List of messages
            **kwargs: Additional arguments
        """
        await self._execute_with_tracking(
            "batch_publish",
            self._worker.batch_publish,
            topic,
            messages,
            **kwargs,
            metadata={"topic": topic, "count": len(messages)},
        )

    async def subscribe(
        self,
        topics: List[str],
        group_id: str,
        **kwargs: Any,
    ) -> None:
        """
        Subscribe to topics.

        Args:
            topics: List of topics to subscribe to
            group_id: Consumer group ID
            **kwargs: Additional arguments
        """
        await self._execute_with_tracking(
            "subscribe",
            self._worker.subscribe,
            topics,
            group_id,
            **kwargs,
            metadata={"topics": topics, "group_id": group_id},
        )

    async def consume(self) -> Any:
        """
        Consume next message from queue.

        Returns:
            Message from queue
        """
        return await self._execute_with_tracking(
            "consume",
            self._worker.consume,
        )
