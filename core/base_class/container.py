"""
Dependency Injection container with config-driven initialization.

This module provides a high-level API for managing connectors lifecycle:
- Registration from factories
- Initialization and shutdown
- Health checks
- Service location
"""
from __future__ import annotations

from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from core.config import Config, get_config
from core.base_class.registry import DIContainer, ConnectorType
from core.base_class.factories import (
    create_llm_connector,
    create_queue_connector,
    create_storage_connector,
    create_db_connector,
    create_all_connectors,
)


class ServiceContainer:
    """
    High-level service container that manages connector lifecycle.

    Usage:
        # Initialize on application startup
        container = ServiceContainer.from_config()
        await container.initialize_all()

        # Use in handlers/services
        llm = container.get_llm("gigachat")
        await llm.chat("Hello")

        # Graceful shutdown
        await container.shutdown_all()
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize service container.

        Args:
            config: Optional config instance (uses get_config() if None)
        """
        self.config = config or get_config()
        self._container = DIContainer()
        self._executor: Optional[ThreadPoolExecutor] = None

    @classmethod
    async def from_config(
        cls,
        config: Optional[Config] = None,
        auto_initialize: bool = True,
    ) -> ServiceContainer:
        """
        Create and optionally initialize container from config.

        Args:
            config: Optional config instance
            auto_initialize: If True, initialize all connectors immediately

        Returns:
            Configured ServiceContainer instance
        """
        instance = cls(config)
        await instance.register_all()

        if auto_initialize:
            await instance.initialize_all()

        return instance

    async def register_all(self) -> None:
        """
        Register all connectors from config (respects feature flags).

        This creates connector instances but doesn't initialize them.
        """
        # Create shared executor for connectors that need it
        self._executor = ThreadPoolExecutor(max_workers=20)

        # Register LLM connector (always enabled)
        llm_connector = create_llm_connector(
            self.config, executor=self._executor
        )
        self._container.register(
            llm_connector, ConnectorType.LLM, name="gigachat"
        )

        # Register queue connector (if enabled)
        if self.config.enable_kafka:
            queue_connector = create_queue_connector(self.config)
            self._container.register(
                queue_connector, ConnectorType.QUEUE, name="kafka"
            )

        # Register storage connector (if enabled)
        if self.config.enable_minio:
            storage_connector = create_storage_connector(
                self.config, executor=self._executor
            )
            self._container.register(
                storage_connector, ConnectorType.STORAGE, name="minio"
            )

        # Register DB connector (if enabled)
        if self.config.enable_database:
            db_connector = create_db_connector(self.config)
            self._container.register(
                db_connector, ConnectorType.DB, name="postgres"
            )

    async def initialize_all(self) -> dict:
        """
        Initialize all registered connectors.

        Returns:
            Dict with initialization results per connector type
        """
        return await self._container.initialize_all()

    async def shutdown_all(self) -> None:
        """Shutdown all connectors and cleanup resources"""
        await self._container.shutdown_all()

        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None

    async def health_check_all(self) -> dict:
        """
        Check health of all connectors.

        Returns:
            Dict with health status per connector type
        """
        return await self._container.health_check_all()

    # Convenience methods for service location

    def get_llm(self, name: str = "gigachat"):
        """Get LLM connector by name"""
        return self._container.get_llm(name)

    def get_queue(self, name: str = "kafka"):
        """Get queue connector by name"""
        return self._container.get_queue(name)

    def get_storage(self, name: str = "minio"):
        """Get storage connector by name"""
        return self._container.get_storage(name)

    def get_db(self, name: str = "postgres"):
        """Get DB connector by name"""
        return self._container.get_db(name)

    # Direct container access for advanced usage

    @property
    def container(self) -> DIContainer:
        """Access underlying DI container"""
        return self._container


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
        auto_initialize: If True, initialize connectors

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

