"""
Core base classes for connectors.

Provides:
- Base connector abstractions
- Protocol-based type definitions
- Registry and DI container
- Config-driven factories
"""
from __future__ import annotations

# Base connector classes
from .connectors import (
    BaseConnector,
    LLMConnector,
    QueueConnector,
    FileStorageConnector,
    DBConnector,
)

# Protocol-based type definitions
from .protocols import (
    ILLMConnector,
    IQueueConnector,
    IFileStorageConnector,
    IDBConnector,
)

# Registry and DI
from .registry import (
    ConnectorType,
    ConnectorRegistry,
    DIContainer,
)

# Factories
from .factories import (
    create_llm_connector,
    create_queue_connector,
    create_storage_connector,
    create_db_connector,
    create_all_connectors,
)

# High-level service container (works with interfaces)
from .service_container import (
    ServiceContainer,
    get_container,
    reset_container,
)

# Interface factories
from .interface_factories import (
    create_llm_interface,
    create_queue_interface,
    create_storage_interface,
    create_db_interface,
    create_all_interfaces,
)

# Observer pattern
from .observer import (
    EventPublisher,
    EventObserver,
    ConnectorEvent,
    EventType,
    LoggingObserver,
    MetricsObserver,
    TracingObserver,
)

__all__ = [
    # Base classes
    "BaseConnector",
    "LLMConnector",
    "QueueConnector",
    "FileStorageConnector",
    "DBConnector",
    # Protocols
    "ILLMConnector",
    "IQueueConnector",
    "IFileStorageConnector",
    "IDBConnector",
    # Registry
    "ConnectorType",
    "ConnectorRegistry",
    "DIContainer",
    # Worker factories
    "create_llm_connector",
    "create_queue_connector",
    "create_storage_connector",
    "create_db_connector",
    "create_all_connectors",
    # Interface factories
    "create_llm_interface",
    "create_queue_interface",
    "create_storage_interface",
    "create_db_interface",
    "create_all_interfaces",
    # Container
    "ServiceContainer",
    "get_container",
    "reset_container",
    # Observer pattern
    "EventPublisher",
    "EventObserver",
    "ConnectorEvent",
    "EventType",
    "LoggingObserver",
    "MetricsObserver",
    "TracingObserver",
]

