"""
Queue Interface - Strategy pattern implementation for message queue connectors.

Allows switching between different queue providers (Kafka, RabbitMQ, Redis, etc.)
while maintaining the same API.
"""
from typing import Any, Dict, List

from core.base_class.connectors import QueueConnector
from core.base_class.observer import EventPublisher
from interface.base import BaseInterface


class QueueInterface(BaseInterface):
    """
    High-level interface for message queue operations.
    
    Implements Strategy pattern - can switch between different queue providers
    (Kafka, RabbitMQ, Redis, etc.) transparently.
    """

    def __init__(
        self,
        worker: QueueConnector,
        name: Optional[str] = None,
        event_publisher: Optional[EventPublisher] = None,
    ):
        """
        Initialize Queue interface.

        Args:
            worker: Queue connector instance (e.g., KafkaConnector)
            name: Interface name (defaults to worker name)
            event_publisher: Optional event publisher for observability
        """
        super().__init__(worker, name, event_publisher)

    @property
    def worker(self) -> QueueConnector:
        """Get underlying queue connector"""
        return self._worker

    async def publish(
        self,
        topic: str,
        datagram_id: str,
        data: Dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """
        Publish message to queue.

        Args:
            topic: Topic/queue name
            datagram_id: Unique message ID
            data: Message data
            **kwargs: Additional arguments
        """
        await self._execute_with_tracking(
            "publish",
            self._worker.publish,
            topic,
            datagram_id,
            data,
            **kwargs,
            metadata={"topic": topic, "datagram_id": datagram_id},
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
