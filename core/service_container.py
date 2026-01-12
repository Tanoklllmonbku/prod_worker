"""
Service Container - manages interfaces with observer pattern support.

This is the high-level container that:
- Manages interfaces (not connectors directly)
- Provides event publishing (Observer pattern)
- Handles lifecycle (initialization, shutdown)
- Provides service location
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from config.config import Settings, get_settings
from core.factories import create_all_interfaces
from core.task_deduplication_queue import TaskDeduplicationQueue
from interface.db import DBInterface
from interface.llm import LLMInterface
from interface.queue import QueueInterface
from interface.storage import StorageInterface
from utils.logging import get_logger_from_config
from utils.observer import (
    EventPublisher,
    LoggingObserver,
    MetricsObserver,
    TracingObserver,
)


class ServiceContainer:
    """
    High-level service container managing interfaces with observer pattern.

    Features:
    - Works with interfaces (Strategy pattern support)
    - Event publishing for all operations (Observer pattern)
    - Centralized logging and metrics
    - Lifecycle management
    """

    def __init__(
        self,
        config: Optional[Settings] = None,
        enable_logging: bool = True,
        enable_metrics: bool = True,
        enable_tracing: bool = False,
    ) -> None:
        """
        Initialize service container.

        Args:
            config: Optional settings instance (uses get_settings() if None)
            enable_logging: Enable logging observer
            enable_metrics: Enable metrics observer
            enable_tracing: Enable tracing observer
        """
        self.config: Settings = config or get_settings()
        self._executor: Optional[ThreadPoolExecutor] = None

        # Event publisher with observers
        self._event_publisher = EventPublisher()
        self._logger = get_logger_from_config(self.config)

        if enable_logging:
            self._event_publisher.subscribe(LoggingObserver(self._logger))

        if enable_metrics:
            self._metrics_observer = MetricsObserver()
            self._event_publisher.subscribe(self._metrics_observer)
        else:
            self._metrics_observer = None

        if enable_tracing:
            self._tracing_observer = TracingObserver()
            self._event_publisher.subscribe(self._tracing_observer)
        else:
            self._tracing_observer = None

        # Store interfaces
        self._interfaces: Dict[str, Any] = {}

        # Task deduplication queue
        self._task_deduplication_queue: Optional[TaskDeduplicationQueue] = None

    @classmethod
    async def from_config(
        cls,
        config: Optional[Settings] = None,
        auto_initialize: bool = True,
        enable_logging: bool = True,
        enable_metrics: bool = True,
        enable_tracing: bool = False,
    ) -> "ServiceContainer":
        """
        Create and optionally initialize container from settings.

        Args:
            config: Optional settings instance
            auto_initialize: If True, initialize all interfaces immediately
            enable_logging: Enable logging observer
            enable_metrics: Enable metrics observer
            enable_tracing: Enable tracing observer
        """
        instance = cls(
            config=config,
            enable_logging=enable_logging,
            enable_metrics=enable_metrics,
            enable_tracing=enable_tracing,
        )
        instance.register_all()

        if auto_initialize:
            await instance.initialize_all()

        return instance

    def register_all(self) -> None:
        """
        Register all interfaces from config (respects feature flags).

        This creates interface instances with appropriate workers but doesn't initialize them.
        """
        self._executor = ThreadPoolExecutor(max_workers=20)

        interfaces = create_all_interfaces(
            config=self.config,
            event_publisher=self._event_publisher,
            executor=self._executor,
        )

        self._interfaces.update(interfaces)

        self._logger.info(
            "Registered %d interfaces: %s",
            len(interfaces),
            list(interfaces.keys()),
        )

    async def initialize_all(self) -> Dict[str, bool]:
        """
        Initialize all registered interfaces.

        Returns:
            Dict mapping interface names to initialization success status
        """
        results: Dict[str, bool] = {}

        for name, interface in self._interfaces.items():
            try:
                await interface.initialize()
                results[name] = True
                self._logger.info("Initialized interface: %s", name)
            except Exception as e:
                results[name] = False
                self._logger.error("Failed to initialize interface %s: %s", name, e)

        return results

    async def shutdown_all(self) -> None:
        """Shutdown all interfaces and cleanup resources"""
        for name, interface in self._interfaces.items():
            try:
                await interface.shutdown()
                self._logger.info("Shutdown interface: %s", name)
            except Exception as e:
                self._logger.error("Error shutting down interface %s: %s", name, e)

        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None

    async def health_check_all(self) -> Dict[str, bool]:
        """
        Check health of all interfaces.

        Returns:
            Dict mapping interface names to health status
        """
        results: Dict[str, bool] = {}

        for name, interface in self._interfaces.items():
            try:
                results[name] = await interface.health_check()
            except Exception:
                results[name] = False

        return results

    # Service location methods

    def get_llm(self, name: str = "llm") -> LLMInterface:
        """Get LLM interface by name"""
        interface = self._interfaces.get(name)
        if interface is None:
            raise KeyError(f"LLM interface '{name}' not found")
        if not isinstance(interface, LLMInterface):
            raise TypeError(f"Interface '{name}' is not an LLMInterface")
        return interface

    def get_queue(self, name: str = "queue") -> QueueInterface:
        """Get Queue interface by name"""
        interface = self._interfaces.get(name)
        if interface is None:
            raise KeyError(f"Queue interface '{name}' not found")
        if not isinstance(interface, QueueInterface):
            raise TypeError(f"Interface '{name}' is not a QueueInterface")
        return interface

    def get_storage(self, name: str = "storage") -> StorageInterface:
        """Get Storage interface by name"""
        interface = self._interfaces.get(name)
        if interface is None:
            raise KeyError(f"Storage interface '{name}' not found")
        if not isinstance(interface, StorageInterface):
            raise TypeError(f"Interface '{name}' is not a StorageInterface")
        return interface

    def get_db(self, name: str = "db") -> DBInterface:
        """Get DB interface by name"""
        interface = self._interfaces.get(name)
        if interface is None:
            raise KeyError(f"DB interface '{name}' not found")
        if not isinstance(interface, DBInterface):
            raise TypeError(f"Interface '{name}' is not a DBInterface")
        return interface

    # Observer access

    @property
    def event_publisher(self) -> EventPublisher:
        """Get event publisher for custom observers"""
        return self._event_publisher

    def get_metrics(self) -> Optional[Dict[str, Dict[str, float]]]:
        """Get collected metrics (if metrics observer enabled)"""
        if self._metrics_observer:
            return self._metrics_observer.get_metrics()
        return None

    def get_traces(self, limit: int = 100) -> Optional[list]:
        """Get recent traces (if tracing observer enabled)"""
        if self._tracing_observer:
            return self._tracing_observer.get_traces(limit)
        return None

    def initialize_task_deduplication_queue(self, max_size: int = 50) -> None:
        """Initialize task deduplication queue"""
        self._task_deduplication_queue = TaskDeduplicationQueue(max_size=max_size)

    def get_task_deduplication_queue(self) -> Optional["TaskDeduplicationQueue"]:
        """Get task deduplication queue"""
        return self._task_deduplication_queue

    def add_task_to_deduplication_queue(self, task_id: str) -> bool:
        """Add task to deduplication queue, returns True if new, False if duplicate"""
        if self._task_deduplication_queue:
            return self._task_deduplication_queue.add_task(task_id)
        return True  # If no queue, treat as new task

    def is_task_duplicate(self, task_id: str) -> bool:
        """Check if task is duplicate"""
        if self._task_deduplication_queue:
            return self._task_deduplication_queue.is_duplicate(task_id)
        return False


async def get_container(
    config: Optional[Settings] = None,
    auto_initialize: bool = True,
) -> ServiceContainer:
    """
    Get or create global service container instance.

    Args:
        config: Optional settings instance
        auto_initialize: If True, initialize interfaces
    """
    global _global_container

    if _global_container is None:
        _global_container = await ServiceContainer.from_config(
            config=config,
            auto_initialize=auto_initialize,
        )

    return _global_container


async def reset_container() -> None:
    """Reset global container (useful for testing)"""
    global _global_container

    if _global_container is not None:
        await _global_container.shutdown_all()
        _global_container = None
