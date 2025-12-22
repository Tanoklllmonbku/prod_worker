"""
Service Container - manages interfaces with observer pattern support.

This is the high-level container that:
- Manages interfaces (not connectors directly)
- Provides event publishing (Observer pattern)
- Handles lifecycle (initialization, shutdown)
- Provides service location
"""
from __future__ import annotations

from typing import Optional, Dict
from concurrent.futures import ThreadPoolExecutor

from core.config import Config, get_config
from core.logging import get_logger_from_config
from core.base_class.observer import (
    EventPublisher,
    LoggingObserver,
    MetricsObserver,
    TracingObserver,
)
from core.base_class.interface_factories import (
    create_llm_interface,
    create_queue_interface,
    create_storage_interface,
    create_db_interface,
    create_all_interfaces,
)

from interface.llm import LLMInterface
from interface.queue import QueueInterface
from interface.storage import StorageInterface
from interface.db import DBInterface


class ServiceContainer:
    """
    High-level service container managing interfaces with observer pattern.

    Features:
    - Works with interfaces (Strategy pattern support)
    - Event publishing for all operations (Observer pattern)
    - Centralized logging and metrics
    - Lifecycle management

    Usage:
        # Initialize on application startup
        container = await ServiceContainer.from_config()

        # Use interfaces
        llm = container.get_llm()
        response = await llm.chat("Hello")

        # Graceful shutdown
        await container.shutdown_all()
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        enable_logging: bool = True,
        enable_metrics: bool = True,
        enable_tracing: bool = False,
    ):
        """
        Initialize service container.

        Args:
            config: Optional config instance (uses get_config() if None)
            enable_logging: Enable logging observer
            enable_metrics: Enable metrics observer
            enable_tracing: Enable tracing observer
        """
        self.config = config or get_config()
        self._executor: Optional[ThreadPoolExecutor] = None

        # Create event publisher with observers
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
        self._interfaces: Dict[str, any] = {}

    @classmethod
    async def from_config(
        cls,
        config: Optional[Config] = None,
        auto_initialize: bool = True,
        enable_logging: bool = True,
        enable_metrics: bool = True,
        enable_tracing: bool = False,
    ) -> ServiceContainer:
        """
        Create and optionally initialize container from config.

        Args:
            config: Optional config instance
            auto_initialize: If True, initialize all interfaces immediately
            enable_logging: Enable logging observer
            enable_metrics: Enable metrics observer
            enable_tracing: Enable tracing observer

        Returns:
            Configured ServiceContainer instance
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
        # Create shared executor for connectors that need it
        self._executor = ThreadPoolExecutor(max_workers=20)

        # Create all interfaces using factories
        interfaces = create_all_interfaces(
            self.config,
            event_publisher=self._event_publisher,
            executor=self._executor,
        )

        self._interfaces.update(interfaces)

        self._logger.info(
            f"Registered {len(interfaces)} interfaces: {list(interfaces.keys())}"
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
                self._logger.info(f"Initialized interface: {name}")
            except Exception as e:
                results[name] = False
                self._logger.error(f"Failed to initialize interface {name}: {e}")

        return results

    async def shutdown_all(self) -> None:
        """Shutdown all interfaces and cleanup resources"""
        for name, interface in self._interfaces.items():
            try:
                await interface.shutdown()
                self._logger.info(f"Shutdown interface: {name}")
            except Exception as e:
                self._logger.error(f"Error shutting down interface {name}: {e}")

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
        if name not in self._interfaces:
            raise KeyError(f"LLM interface '{name}' not found")
        interface = self._interfaces[name]
        if not isinstance(interface, LLMInterface):
            raise TypeError(f"Interface '{name}' is not an LLMInterface")
        return interface

    def get_queue(self, name: str = "queue") -> QueueInterface:
        """Get Queue interface by name"""
        if name not in self._interfaces:
            raise KeyError(f"Queue interface '{name}' not found")
        interface = self._interfaces[name]
        if not isinstance(interface, QueueInterface):
            raise TypeError(f"Interface '{name}' is not a QueueInterface")
        return interface

    def get_storage(self, name: str = "storage") -> StorageInterface:
        """Get Storage interface by name"""
        if name not in self._interfaces:
            raise KeyError(f"Storage interface '{name}' not found")
        interface = self._interfaces[name]
        if not isinstance(interface, StorageInterface):
            raise TypeError(f"Interface '{name}' is not a StorageInterface")
        return interface

    def get_db(self, name: str = "db") -> DBInterface:
        """Get DB interface by name"""
        if name not in self._interfaces:
            raise KeyError(f"DB interface '{name}' not found")
        interface = self._interfaces[name]
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


# Global singleton instance (optional, for convenience)
_global_container: Optional[ServiceContainer] = None


async def get_container(
    config: Optional[Config] = None,
    auto_initialize: bool = True,
) -> ServiceContainer:
    """
    Get or create global service container instance.

    Args:
        config: Optional config instance
        auto_initialize: If True, initialize interfaces

    Returns:
        Global ServiceContainer instance
    """
    global _global_container

    if _global_container is None:
        _global_container = await ServiceContainer.from_config(
            config=config, auto_initialize=auto_initialize
        )

    return _global_container


async def reset_container() -> None:
    """Reset global container (useful for testing)"""
    global _global_container

    if _global_container is not None:
        await _global_container.shutdown_all()
        _global_container = None

