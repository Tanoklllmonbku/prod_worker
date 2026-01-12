"""
Registry-based Dependency Injection container.

Supports:
- Type-safe registration and lookup
- Multi-key lookup (type + name)
- Lazy initialization
- Health checks aggregation
- Graceful shutdown
"""
from __future__ import annotations

from typing import Dict, TypeVar, Generic, Optional, List, Set
from enum import Enum

from .base_connectors import BaseConnector


T = TypeVar("T", bound=BaseConnector)


class ConnectorType(str, Enum):
    """Connector type identifiers"""
    LLM = "llm"
    QUEUE = "queue"
    STORAGE = "storage"
    DB = "db"


class ConnectorRegistry(Generic[T]):
    """
    Type-safe registry for connectors of a given type.
    Provides O(1) lookup by name.
    """

    def __init__(self) -> None:
        self._items: Dict[str, T] = {}
        self._initialized: Set[str] = set()

    def register(self, connector: T, name: Optional[str] = None) -> None:
        """
        Register a connector instance.

        Args:
            connector: Connector instance
            name: Optional override name (defaults to connector.name)
        """
        key = name or connector.name
        self._items[key] = connector

    def get(self, name: str) -> T:
        """
        Get connector by name.

        Args:
            name: Connector name

        Returns:
            Connector instance

        Raises:
            KeyError: If connector not found
        """
        if name not in self._items:
            raise KeyError(f"Connector '{name}' not found in registry")
        return self._items[name]

    def get_or_none(self, name: str) -> Optional[T]:
        """Get connector by name, return None if not found"""
        return self._items.get(name)

    def all(self) -> Dict[str, T]:
        """Get all registered connectors"""
        return dict(self._items)

    def names(self) -> List[str]:
        """Get list of all registered connector names"""
        return list(self._items.keys())

    def has(self, name: str) -> bool:
        """Check if connector is registered"""
        return name in self._items

    async def initialize_all(self) -> Dict[str, bool]:
        """
        Initialize all registered connectors.

        Returns:
            Dict mapping connector names to initialization success status
        """
        results: Dict[str, bool] = {}
        for name, connector in self._items.items():
            if name not in self._initialized:
                try:
                    await connector.initialize()
                    self._initialized.add(name)
                    results[name] = True
                except Exception:
                    results[name] = False
        return results

    async def shutdown_all(self) -> None:
        """Shutdown all registered connectors"""
        for name, connector in self._items.items():
            if name in self._initialized:
                try:
                    await connector.shutdown()
                    self._initialized.discard(name)
                except Exception:
                    pass  # Log but don't fail

    async def health_check_all(self) -> Dict[str, bool]:
        """Check health of all connectors"""
        results: Dict[str, bool] = {}
        for name, connector in self._items.items():
            if name in self._initialized:
                try:
                    results[name] = await connector.health_check()
                except Exception:
                    results[name] = False
        return results


class DIContainer:
    """
    Dependency Injection container supporting multi-type registry.

    Provides:
    - Type-safe registration and lookup
    - O(1) lookup by (type, name) key
    - Aggregated lifecycle management
    - Health checks across all connectors
    """

    def __init__(self) -> None:
        self._llm_registry = ConnectorRegistry[BaseConnector]()
        self._queue_registry = ConnectorRegistry[BaseConnector]()
        self._storage_registry = ConnectorRegistry[BaseConnector]()
        self._db_registry = ConnectorRegistry[BaseConnector]()

        self._type_to_registry: Dict[ConnectorType, ConnectorRegistry] = {
            ConnectorType.LLM: self._llm_registry,
            ConnectorType.QUEUE: self._queue_registry,
            ConnectorType.STORAGE: self._storage_registry,
            ConnectorType.DB: self._db_registry,
        }

    def register(
        self,
        connector: BaseConnector,
        connector_type: ConnectorType,
        name: Optional[str] = None,
    ) -> None:
        """
        Register a connector in the appropriate registry.

        Args:
            connector: Connector instance
            connector_type: Type of connector
            name: Optional override name
        """
        registry = self._type_to_registry[connector_type]
        registry.register(connector, name)

    def get(self, connector_type: ConnectorType, name: str) -> BaseConnector:
        """
        Get connector by type and name.

        Args:
            connector_type: Type of connector
            name: Connector name

        Returns:
            Connector instance
        """
        registry = self._type_to_registry[connector_type]
        return registry.get(name)

    def get_llm(self, name: str) -> BaseConnector:
        """Get LLM connector by name"""
        return self._llm_registry.get(name)

    def get_queue(self, name: str) -> BaseConnector:
        """Get queue connector by name"""
        return self._queue_registry.get(name)

    def get_storage(self, name: str) -> BaseConnector:
        """Get storage connector by name"""
        return self._storage_registry.get(name)

    def get_db(self, name: str) -> BaseConnector:
        """Get DB connector by name"""
        return self._db_registry.get(name)

    async def initialize_all(self) -> Dict[ConnectorType, Dict[str, bool]]:
        """
        Initialize all connectors across all registries.

        Returns:
            Nested dict: {connector_type: {name: success}}
        """
        results: Dict[ConnectorType, Dict[str, bool]] = {}
        for conn_type, registry in self._type_to_registry.items():
            results[conn_type] = await registry.initialize_all()
        return results

    async def shutdown_all(self) -> None:
        """Shutdown all connectors"""
        for registry in self._type_to_registry.values():
            await registry.shutdown_all()

    async def health_check_all(self) -> Dict[ConnectorType, Dict[str, bool]]:
        """Check health of all connectors"""
        results: Dict[ConnectorType, Dict[str, bool]] = {}
        for conn_type, registry in self._type_to_registry.items():
            results[conn_type] = await registry.health_check_all()
        return results
