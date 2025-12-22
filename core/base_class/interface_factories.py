"""
Factories for creating interfaces with appropriate workers.

These factories select the right worker based on configuration and wrap it
in an interface for Strategy pattern support.
"""
from __future__ import annotations

from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from core.config import Config
from core.base_class.observer import EventPublisher
from core.base_class.factories import (
    create_llm_connector,
    create_queue_connector,
    create_storage_connector,
    create_db_connector,
)

from interface.llm import LLMInterface
from interface.queue import QueueInterface
from interface.storage import StorageInterface
from interface.db import DBInterface


def create_llm_interface(
    config: Config,
    name: str = "llm",
    event_publisher: Optional[EventPublisher] = None,
    executor: Optional[ThreadPoolExecutor] = None,
) -> LLMInterface:
    """
    Create LLM interface with worker selected from config.

    Currently supports:
    - GigaChat (default)

    Future: Can be extended to support OpenAI, Anthropic, etc. based on config.

    Args:
        config: Application configuration
        name: Interface name
        event_publisher: Optional event publisher for observability
        executor: Optional thread pool executor

    Returns:
        LLMInterface instance
    """
    # Select worker based on config (future: config.llm_provider)
    worker = create_llm_connector(config, executor=executor)

    return LLMInterface(
        worker=worker,
        name=name,
        event_publisher=event_publisher,
    )


def create_queue_interface(
    config: Config,
    name: str = "queue",
    event_publisher: Optional[EventPublisher] = None,
) -> QueueInterface:
    """
    Create Queue interface with worker selected from config.

    Currently supports:
    - Kafka (default)

    Future: Can be extended to support RabbitMQ, Redis, etc. based on config.

    Args:
        config: Application configuration
        name: Interface name
        event_publisher: Optional event publisher for observability

    Returns:
        QueueInterface instance
    """
    # Select worker based on config (future: config.queue_provider)
    worker = create_queue_connector(config)

    return QueueInterface(
        worker=worker,
        name=name,
        event_publisher=event_publisher,
    )


def create_storage_interface(
    config: Config,
    name: str = "storage",
    event_publisher: Optional[EventPublisher] = None,
    executor: Optional[ThreadPoolExecutor] = None,
) -> StorageInterface:
    """
    Create Storage interface with worker selected from config.

    Currently supports:
    - MinIO (default)

    Future: Can be extended to support S3, Azure Blob, etc. based on config.

    Args:
        config: Application configuration
        name: Interface name
        event_publisher: Optional event publisher for observability
        executor: Optional thread pool executor

    Returns:
        StorageInterface instance
    """
    # Select worker based on config (future: config.storage_provider)
    worker = create_storage_connector(config, executor=executor)

    return StorageInterface(
        worker=worker,
        name=name,
        event_publisher=event_publisher,
    )


def create_db_interface(
    config: Config,
    name: str = "db",
    event_publisher: Optional[EventPublisher] = None,
) -> DBInterface:
    """
    Create DB interface with worker selected from config.

    Currently supports:
    - PostgreSQL (default)

    Future: Can be extended to support MySQL, MongoDB, etc. based on config.

    Args:
        config: Application configuration
        name: Interface name
        event_publisher: Optional event publisher for observability

    Returns:
        DBInterface instance
    """
    # Select worker based on config.db_type
    # For now, only PostgreSQL is supported
    if config.db_type.lower() in ("postgresql", "postgres", "pg"):
        worker = create_db_connector(config)
    else:
        raise ValueError(
            f"Unsupported database type: {config.db_type}. "
            f"Supported: postgresql"
        )

    return DBInterface(
        worker=worker,
        name=name,
        event_publisher=event_publisher,
    )


def create_all_interfaces(
    config: Config,
    event_publisher: Optional[EventPublisher] = None,
    executor: Optional[ThreadPoolExecutor] = None,
) -> dict[str, any]:
    """
    Create all interfaces from config.

    Respects feature flags (enable_minio, enable_database, enable_kafka).

    Args:
        config: Application configuration
        event_publisher: Optional event publisher for observability
        executor: Optional shared thread pool executor

    Returns:
        Dict mapping interface names to instances:
        {
            "llm": LLMInterface,
            "queue": QueueInterface (if enabled),
            "storage": StorageInterface (if enabled),
            "db": DBInterface (if enabled),
        }
    """
    interfaces = {}

    # LLM interface (always created)
    interfaces["llm"] = create_llm_interface(
        config, event_publisher=event_publisher, executor=executor
    )

    # Queue interface (if enabled)
    if config.enable_kafka:
        interfaces["queue"] = create_queue_interface(
            config, event_publisher=event_publisher
        )

    # Storage interface (if enabled)
    if config.enable_minio:
        interfaces["storage"] = create_storage_interface(
            config, event_publisher=event_publisher, executor=executor
        )

    # DB interface (if enabled)
    if config.enable_database:
        interfaces["db"] = create_db_interface(
            config, event_publisher=event_publisher
        )

    return interfaces

