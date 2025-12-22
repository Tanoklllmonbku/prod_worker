"""
Config-driven factories for connector instantiation.

These factories read configuration from core.config.Config and create
properly configured connector instances. They're used by the DI container
to initialize connectors on application startup.
"""
from __future__ import annotations

from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from core.config import Config
from core.logging import get_logger_from_config
from core.base_class.registry import ConnectorType
from core.connector_configs import (
    LLMConnectorConfig,
    DBConnectorConfig,
    QueueConnectorConfig,
    StorageConnectorConfig,
)

from connectors.gigachat_connector import GigaChatConnector
from connectors.kafka_connector import KafkaConnector, SerializationFormat
from connectors.minio_connector import MinIOConnector
from connectors.pg_connector import PGConnector


def create_llm_connector(
    config: Config,
    connector_config: Optional[LLMConnectorConfig] = None,
    name: str = "gigachat",
    executor: Optional[ThreadPoolExecutor] = None,
) -> GigaChatConnector:
    """
    Factory for creating GigaChat LLM connector from config.

    Args:
        config: Application configuration
        connector_config: Optional LLM connector config (uses config.connectors_config.llm if None)
        name: Connector name (default: "gigachat")
        executor: Optional thread pool executor (creates new if None)

    Returns:
        Configured GigaChatConnector instance
    """
    logger = get_logger_from_config(config)

    # Use provided config or get from config.connectors_config
    if connector_config is None:
        if config.connectors_config and config.connectors_config.llm:
            connector_config = config.connectors_config.llm
        else:
            # Fallback to defaults - create new config with defaults
            connector_config = LLMConnectorConfig()

    # Get auth key from keyring (sensitive data should be in keyring, not JSON)
    auth_key = connector_config.auth_key or config.gigachat_token

    connector = GigaChatConnector(
        get_logger=lambda: logger,
        executor=executor,
        auth_key=auth_key,
        access_token=connector_config.access_token,
        model=connector_config.model,
        scope=connector_config.scope,
        verify_ssl=connector_config.verify_ssl,
        timeout=connector_config.timeout,
        max_connections=connector_config.max_connections,
    )

    return connector


def create_queue_connector(
    config: Config,
    connector_config: Optional[QueueConnectorConfig] = None,
    name: str = "kafka",
) -> KafkaConnector:
    """
    Factory for creating Kafka queue connector from config.

    Args:
        config: Application configuration
        connector_config: Optional Queue connector config (uses config.connectors_config.queue if None)
        name: Connector name (default: "kafka")

    Returns:
        Configured KafkaConnector instance
    """
    logger = get_logger_from_config(config)

    # Use provided config or get from config.connectors_config
    if connector_config is None:
        if config.connectors_config and config.connectors_config.queue:
            connector_config = config.connectors_config.queue
        else:
            # Fallback to defaults or legacy config
            bootstrap_servers = [
                s.strip() for s in config.kafka_bootstrap_servers.split(",")
            ]
            connector_config = QueueConnectorConfig(
                bootstrap_servers=bootstrap_servers,
                default_format="json",
                consumer_poll_timeout=1.0,
            )

    # Convert format string to enum
    format_map = {
        "json": SerializationFormat.JSON,
        "msgpack": SerializationFormat.MSGPACK,
    }
    default_format = format_map.get(
        connector_config.default_format.lower(), SerializationFormat.JSON
    )

    connector = KafkaConnector(
        bootstrap_servers=connector_config.bootstrap_servers,
        logger=logger,
        default_format=default_format,
        consumer_poll_timeout=connector_config.consumer_poll_timeout,
    )

    return connector


def create_storage_connector(
    config: Config,
    connector_config: Optional[StorageConnectorConfig] = None,
    name: str = "minio",
    executor: Optional[ThreadPoolExecutor] = None,
) -> MinIOConnector:
    """
    Factory for creating MinIO storage connector from config.

    Args:
        config: Application configuration
        connector_config: Optional Storage connector config (uses config.connectors_config.storage if None)
        name: Connector name (default: "minio")
        executor: Optional thread pool executor (creates new if None)

    Returns:
        Configured MinIOConnector instance
    """
    logger = get_logger_from_config(config)

    # Use provided config or get from config.connectors_config
    if connector_config is None:
        if config.connectors_config and config.connectors_config.storage:
            connector_config = config.connectors_config.storage
        else:
            # Fallback to defaults or legacy config
            connector_config = StorageConnectorConfig(
                endpoint=config.minio_endpoint,
                access_key=config.minio_access_key,
                secret_key=config.minio_secret_key,
                bucket=config.minio_bucket,
                use_ssl=config.minio_use_ssl,
            )

    if executor is None:
        executor = ThreadPoolExecutor(max_workers=10)

    connector = MinIOConnector(
        endpoint=connector_config.endpoint,
        access_key=connector_config.access_key,
        secret_key=connector_config.secret_key,
        bucket=connector_config.bucket,
        get_logger=lambda: logger,
        executor=executor,
        use_ssl=connector_config.use_ssl,
    )

    return connector


def create_db_connector(
    config: Config,
    connector_config: Optional[DBConnectorConfig] = None,
    name: str = "postgres",
) -> PGConnector:
    """
    Factory for creating PostgreSQL database connector from config.

    Args:
        config: Application configuration
        connector_config: Optional DB connector config (uses config.connectors_config.db if None)
        name: Connector name (default: "postgres")

    Returns:
        Configured PGConnector instance
    """
    logger = get_logger_from_config(config)

    # Use provided config or get from config.connectors_config
    if connector_config is None:
        if config.connectors_config and config.connectors_config.db:
            connector_config = config.connectors_config.db
        else:
            # Fallback to defaults or legacy config
            connector_config = DBConnectorConfig(
                host=config.db_host,
                port=config.db_port,
                database=config.db_name,
                user=config.db_user,
                password=config.db_password,
                min_pool_size=config.db_pool_size,
                max_pool_size=config.db_max_overflow,
            )

    connector = PGConnector(
        host=connector_config.host,
        port=connector_config.port,
        database=connector_config.database,
        user=connector_config.user,
        password=connector_config.password,
        min_pool_size=connector_config.min_pool_size,
        max_pool_size=connector_config.max_pool_size,
        logger=logger,
    )

    return connector


def create_all_connectors(
    config: Config,
    executor: Optional[ThreadPoolExecutor] = None,
) -> dict[str, any]:
    """
    Factory function to create all connectors from config.

    Respects feature flags (enable_minio, enable_database, enable_kafka).

    Args:
        config: Application configuration
        executor: Optional shared thread pool executor

    Returns:
        Dict mapping connector names to instances:
        {
            "llm": GigaChatConnector,
            "queue": KafkaConnector (if enabled),
            "storage": MinIOConnector (if enabled),
            "db": PGConnector (if enabled),
        }
    """
    connectors = {}

    # LLM connector (always created)
    connectors["llm"] = create_llm_connector(config, executor=executor)

    # Queue connector (if enabled)
    if config.enable_kafka:
        connectors["queue"] = create_queue_connector(config)

    # Storage connector (if enabled)
    if config.enable_minio:
        connectors["storage"] = create_storage_connector(
            config, executor=executor
        )

    # DB connector (if enabled)
    if config.enable_database:
        connectors["db"] = create_db_connector(config)

    return connectors

