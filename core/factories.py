from concurrent.futures import ThreadPoolExecutor
from typing import Any, Awaitable, Callable, Dict, Optional

from config.config import Settings, get_settings
from connectors.gigachat_connector import GigaChatConnector
from connectors.http_connector import FastApiConnector
from connectors.kafka_connector import KafkaConnector
from connectors.minio_connector import MinIOConnector
from connectors.pg_connector import PGConnector
from core.registry import register_connector, register_interface, get_connector_class, get_interface_class
from interface.db import DBInterface
from interface.http import HTTPInterface
from interface.llm import LLMInterface
from interface.queue import QueueInterface
from interface.storage import StorageInterface
from utils.logging import get_logger_from_config
from utils.observer import EventPublisher


class ConnectorFactory:
    """
    Factory for creating connector instances based on configuration.

    This factory handles the creation of low-level connector objects
    that directly interact with external services like databases,
    message queues, storage systems, etc.
    """

    def __init__(self, config: Settings):
        """
        Initialize the connector factory with configuration.

        Args:
            config: Application settings/configuration object
        """
        self.config: Settings = config

    def _validate_config_exists(self, config_attr: str) -> bool:
        """Validate that the required configuration exists"""
        return hasattr(self.config, config_attr) and getattr(self.config, config_attr) is not None

    def _validate_gigachat_config(self) -> bool:
        """Validate GigaChat configuration"""
        if not self._validate_config_exists('gigachat'):
            return False
        gigachat_cfg = self.config.gigachat
        return all([
            gigachat_cfg.access_token,
            gigachat_cfg.model
        ])

    def _validate_kafka_config(self) -> bool:
        """Validate Kafka configuration"""
        if not self._validate_config_exists('kafka'):
            return False
        kafka_cfg = self.config.kafka
        return bool(kafka_cfg.bootstrap_servers)

    def _validate_minio_config(self) -> bool:
        """Validate MinIO configuration"""
        if not self._validate_config_exists('minio'):
            return False
        minio_cfg = self.config.minio
        return all([
            minio_cfg.endpoint,
            minio_cfg.access_key,
            minio_cfg.secret_key,
            minio_cfg.bucket_name
        ])

    def _validate_postgres_config(self) -> bool:
        """Validate PostgreSQL configuration"""
        if not self._validate_config_exists('postgres'):
            return False
        postgres_cfg = self.config.postgres
        return all([
            postgres_cfg.host,
            postgres_cfg.port,
            postgres_cfg.database,
            postgres_cfg.user,
            postgres_cfg.password
        ])

    def _validate_http_config(self) -> bool:
        """Validate HTTP configuration"""
        if not self._validate_config_exists('http'):
            return False
        http_cfg = self.config.http
        return all([
            http_cfg.host,
            http_cfg.port
        ])

    def create_llm_connector(self, name: str = "GigaChat") -> GigaChatConnector:
        """Create an LLM connector"""
        if not self._validate_gigachat_config():
            raise ValueError("Invalid GigaChat configuration provided")
        # Using the helper function that properly configures the connector
        return _create_llm_connector(self.config)

    def create_queue_connector(self, name: str = "Kafka") -> KafkaConnector:
        """Create a queue connector"""
        if not self._validate_kafka_config():
            raise ValueError("Invalid Kafka configuration provided")
        # Using the helper function that properly configures the connector
        return _create_queue_connector(self.config)

    def create_storage_connector(
        self,
        name: str = "Minio",
        executor: Optional[ThreadPoolExecutor] = None
    ) -> MinIOConnector:
        """Create a storage connector"""
        if not self._validate_minio_config():
            raise ValueError("Invalid MinIO configuration provided")
        # Using the helper function that properly configures the connector
        return _create_storage_connector(self.config, executor=executor)

    def create_db_connector(self, name: str = "Postgres") -> PGConnector:
        """Create a database connector"""
        if not self._validate_postgres_config():
            raise ValueError("Invalid PostgreSQL configuration provided")
        # Using the helper function that properly configures the connector
        return _create_db_connector(self.config)

    def create_http_connector(
        self,
        name: str = "FastApi",
        health_callback: Optional[Callable[[], Awaitable[dict]]] = None,
        status_callback: Optional[Callable[[], Awaitable[dict]]] = None,
    ) -> FastApiConnector:
        """Create an HTTP connector"""
        if not self._validate_http_config():
            raise ValueError("Invalid HTTP configuration provided")
        # Using the helper function that properly configures the connector
        return _create_http_connector(
            self.config,
            health_callback=health_callback,
            status_callback=status_callback
        )

    def create_all_connectors(
        self,
        executor: Optional[ThreadPoolExecutor] = None,
        health_callback: Optional[Callable[[], Awaitable[dict]]] = None,
        status_callback: Optional[Callable[[], Awaitable[dict]]] = None,
    ) -> Dict[str, Any]:
        """Create all available connectors"""
        connectors = {}

        # Create LLM connector
        if self._validate_gigachat_config():
            connectors["GigaChat"] = self.create_llm_connector()

        # Create queue connector
        if self._validate_kafka_config():
            connectors["Kafka"] = self.create_queue_connector()

        # Create storage connector
        if self._validate_minio_config() and getattr(self.config.minio, 'enabled', True):
            connectors["Minio"] = self.create_storage_connector(executor=executor)

        # Create DB connector
        if self._validate_postgres_config() and getattr(self.config.postgres, 'enabled', True):
            connectors["Postgres"] = self.create_db_connector()

        # Create HTTP connector
        if self._validate_http_config() and getattr(self.config.http, 'enabled', True):
            connectors["FastApi"] = self.create_http_connector(
                health_callback=health_callback,
                status_callback=status_callback
            )

        return connectors


class InterfaceFactory:
    """
    Factory for creating interface instances based on configuration.

    This factory handles the creation of high-level interface objects
    that provide a consistent API for interacting with various services
    through their respective connectors, with added functionality like
    logging, monitoring, and error handling.
    """

    def __init__(self, config: Settings):
        """
        Initialize the interface factory with configuration.

        Args:
            config: Application settings/configuration object
        """
        self.config: Settings = config

    def _validate_config_exists(self, config_attr: str) -> bool:
        """Validate that the required configuration exists"""
        return hasattr(self.config, config_attr) and getattr(self.config, config_attr) is not None

    def _validate_gigachat_config(self) -> bool:
        """Validate GigaChat configuration"""
        if not self._validate_config_exists('gigachat'):
            return False
        gigachat_cfg = self.config.gigachat
        return all([
            gigachat_cfg.access_token,
            gigachat_cfg.model
        ])

    def _validate_kafka_config(self) -> bool:
        """Validate Kafka configuration"""
        if not self._validate_config_exists('kafka'):
            return False
        kafka_cfg = self.config.kafka
        return bool(kafka_cfg.bootstrap_servers)

    def _validate_minio_config(self) -> bool:
        """Validate MinIO configuration"""
        if not self._validate_config_exists('minio'):
            return False
        minio_cfg = self.config.minio
        return all([
            minio_cfg.endpoint,
            minio_cfg.access_key,
            minio_cfg.secret_key,
            minio_cfg.bucket_name
        ])

    def _validate_postgres_config(self) -> bool:
        """Validate PostgreSQL configuration"""
        if not self._validate_config_exists('postgres'):
            return False
        postgres_cfg = self.config.postgres
        return all([
            postgres_cfg.host,
            postgres_cfg.port,
            postgres_cfg.database,
            postgres_cfg.user,
            postgres_cfg.password
        ])

    def _validate_http_config(self) -> bool:
        """Validate HTTP configuration"""
        if not self._validate_config_exists('http'):
            return False
        http_cfg = self.config.http
        return all([
            http_cfg.host,
            http_cfg.port
        ])

    def create_llm_interface(
        self,
        name: str = "GigaChat",
        event_publisher: Optional[EventPublisher] = None
    ) -> LLMInterface:
        """Create an LLM interface"""
        if not self._validate_gigachat_config():
            raise ValueError("Invalid GigaChat configuration provided")
        connector = _create_llm_connector(self.config)
        # Using the registered interface class
        interface_class = get_interface_class(name)
        return interface_class(worker=connector, name=name, event_publisher=event_publisher)

    def create_queue_interface(
        self,
        name: str = "Kafka",
        event_publisher: Optional[EventPublisher] = None
    ) -> QueueInterface:
        """Create a queue interface"""
        if not self._validate_kafka_config():
            raise ValueError("Invalid Kafka configuration provided")
        connector = _create_queue_connector(self.config)
        # Using the registered interface class
        interface_class = get_interface_class(name)
        return interface_class(worker=connector, name=name, event_publisher=event_publisher)

    def create_storage_interface(
        self,
        name: str = "Minio",
        event_publisher: Optional[EventPublisher] = None,
        executor: Optional[ThreadPoolExecutor] = None
    ) -> StorageInterface:
        """Create a storage interface"""
        if not self._validate_minio_config():
            raise ValueError("Invalid MinIO configuration provided")
        connector = _create_storage_connector(self.config, executor=executor)
        # Using the registered interface class
        interface_class = get_interface_class(name)
        return interface_class(worker=connector, name=name, event_publisher=event_publisher)

    def create_db_interface(
        self,
        name: str = "Postgres",
        event_publisher: Optional[EventPublisher] = None
    ) -> DBInterface:
        """Create a database interface"""
        if not self._validate_postgres_config():
            raise ValueError("Invalid PostgreSQL configuration provided")
        connector = _create_db_connector(self.config)
        # Using the registered interface class
        interface_class = get_interface_class(name)
        return interface_class(worker=connector, name=name, event_publisher=event_publisher)

    def create_http_interface(
        self,
        name: str = "FastApi",
        event_publisher: Optional[EventPublisher] = None,
        health_callback: Optional[Callable[[], Awaitable[dict]]] = None,
        status_callback: Optional[Callable[[], Awaitable[dict]]] = None,
    ) -> HTTPInterface:
        """Create an HTTP interface"""
        if not self._validate_http_config():
            raise ValueError("Invalid HTTP configuration provided")
        connector = _create_http_connector(
            self.config,
            health_callback=health_callback,
            status_callback=status_callback
        )
        # Using the registered interface class
        interface_class = get_interface_class(name)
        return interface_class(worker=connector, name=name, event_publisher=event_publisher)

    def create_all_interfaces(
        self,
        event_publisher: Optional[EventPublisher] = None,
        executor: Optional[ThreadPoolExecutor] = None,
        health_callback: Optional[Callable[[], Awaitable[dict]]] = None,
        status_callback: Optional[Callable[[], Awaitable[dict]]] = None,
    ) -> Dict[str, Any]:
        """Create all available interfaces"""
        interfaces = {}

        # Create LLM interface
        if self._validate_gigachat_config():
            interfaces["GigaChat"] = self.create_llm_interface(event_publisher=event_publisher)

        # Create queue interface
        if self._validate_kafka_config():
            interfaces["Kafka"] = self.create_queue_interface(event_publisher=event_publisher)

        # Create storage interface
        if self._validate_minio_config() and getattr(self.config.minio, 'enabled', True):
            interfaces["Minio"] = self.create_storage_interface(
                event_publisher=event_publisher,
                executor=executor
            )

        # Create DB interface
        if self._validate_postgres_config() and getattr(self.config.postgres, 'enabled', True):
            interfaces["Postgres"] = self.create_db_interface(event_publisher=event_publisher)

        # Create HTTP interface
        if self._validate_http_config() and getattr(self.config.http, 'enabled', True):
            interfaces["FastApi"] = self.create_http_interface(
                event_publisher=event_publisher,
                health_callback=health_callback,
                status_callback=status_callback
            )

        return interfaces


class ConnectorRegistryFactory:
    """
    Factory for managing connector and interface creation and registration.

    This factory combines both connector and interface creation capabilities
    with a registry functionality to store and retrieve instances by name.
    It serves as a central hub for all connector-related operations in the application.
    """

    def __init__(self, config: Settings):
        """
        Initialize the registry factory with configuration.

        Args:
            config: Application settings/configuration object
        """
        self.config: Settings = config
        self._connectors: Dict[str, Any] = {}
        self._interfaces: Dict[str, Any] = {}

        # Initialize sub-factories
        self.connector_factory = ConnectorFactory(config)
        self.interface_factory = InterfaceFactory(config)

    def register_connector(self, name: str, connector: Any) -> None:
        """Register a connector instance by name"""
        self._connectors[name] = connector

    def get_connector(self, name: str) -> Any:
        """Get a registered connector by name"""
        return self._connectors.get(name)

    def register_interface(self, name: str, interface: Any) -> None:
        """Register an interface instance by name"""
        self._interfaces[name] = interface

    def get_interface(self, name: str) -> Any:
        """Get a registered interface by name"""
        return self._interfaces.get(name)

    def create_and_register_llm_connector(self, name: str = "GigaChat") -> LLMInterface:
        """Create and register an LLM connector"""
        connector = self.connector_factory.create_llm_connector(name)
        self.register_connector(name, connector)
        interface = self.interface_factory.create_llm_interface(name)
        self.register_interface(name, interface)
        return interface

    def create_and_register_queue_connector(self, name: str = "Kafka") -> QueueInterface:
        """Create and register a queue connector"""
        connector = self.connector_factory.create_queue_connector(name)
        self.register_connector(name, connector)
        interface = self.interface_factory.create_queue_interface(name)
        self.register_interface(name, interface)
        return interface

    def create_and_register_storage_connector(
        self,
        name: str = "Minio",
        executor: Optional[ThreadPoolExecutor] = None
    ) -> StorageInterface:
        """Create and register a storage connector"""
        connector = self.connector_factory.create_storage_connector(name, executor=executor)
        self.register_connector(name, connector)
        interface = self.interface_factory.create_storage_interface(name, executor=executor)
        self.register_interface(name, interface)
        return interface

    def create_and_register_db_connector(self, name: str = "Postgres") -> DBInterface:
        """Create and register a database connector"""
        connector = self.connector_factory.create_db_connector(name)
        self.register_connector(name, connector)
        interface = self.interface_factory.create_db_interface(name)
        self.register_interface(name, interface)
        return interface

    def create_and_register_http_connector(
        self,
        name: str = "FastApi",
        health_callback: Optional[Callable[[], Awaitable[dict]]] = None,
        status_callback: Optional[Callable[[], Awaitable[dict]]] = None,
    ) -> HTTPInterface:
        """Create and register an HTTP connector"""
        connector = self.connector_factory.create_http_connector(
            name,
            health_callback=health_callback,
            status_callback=status_callback
        )
        self.register_connector(name, connector)
        interface = self.interface_factory.create_http_interface(
            name,
            health_callback=health_callback,
            status_callback=status_callback
        )
        self.register_interface(name, interface)
        return interface

    def create_and_register_all_connectors(
        self,
        executor: Optional[ThreadPoolExecutor] = None,
        health_callback: Optional[Callable[[], Awaitable[dict]]] = None,
        status_callback: Optional[Callable[[], Awaitable[dict]]] = None,
    ) -> Dict[str, Any]:
        """Create and register all available connectors"""
        # Create all connectors using the connector factory
        connectors = self.connector_factory.create_all_connectors(
            executor=executor,
            health_callback=health_callback,
            status_callback=status_callback
        )

        # Register each connector
        for name, connector in connectors.items():
            self.register_connector(name, connector)

        # Create all interfaces using the interface factory
        interfaces = self.interface_factory.create_all_interfaces(
            executor=executor,
            health_callback=health_callback,
            status_callback=status_callback
        )

        # Register each interface
        for name, interface in interfaces.items():
            self.register_interface(name, interface)

        return interfaces


def _create_llm_connector(
    config: Settings,
) -> GigaChatConnector:
    """
    Создать GigaChat-коннектор из Settings (config.gigachat).
    """
    logger = get_logger_from_config(config)

    return GigaChatConnector(
        get_logger=lambda: logger,
        credentials=config.gigachat.access_token,
        model=config.gigachat.model,
        scope=config.gigachat.scope,
        verify_ssl=config.gigachat.verify_ssl,
        timeout=float(config.gigachat.request_timeout_seconds),
        max_connections=config.gigachat.max_connections,
        base_url=config.gigachat.base_url,
        api_version=config.gigachat.api_version,
        oauth_url=config.gigachat.oauth_url,
    )


def _create_queue_connector(
    config: Settings,
) -> KafkaConnector:
    """
    Создать Kafka-коннектор из Settings (config.kafka).
    """
    logger = get_logger_from_config(config)

    servers_raw = config.kafka.bootstrap_servers
    if isinstance(servers_raw, str):
        bootstrap_servers = [s.strip() for s in servers_raw.split(",") if s.strip()]
    else:
        bootstrap_servers = list(servers_raw)

    return KafkaConnector(
        bootstrap_servers=bootstrap_servers,
        group_id=config.kafka.group_id,
        logger=logger,
        consumer_poll_timeout=config.kafka.consumer_poll_timeout,
    )


def _create_storage_connector(
    config: Settings,
    executor: Optional[ThreadPoolExecutor] = None,
) -> MinIOConnector:
    """
    Создать MinIO-коннектор из Settings (config.minio).
    Сигнатура MinIOConnector.__init__:

    def __init__(
        self,
        endpoint: str,
        accesskey: str,
        secretkey: str,
        bucket: str,
        getlogger,
        executor: ThreadPoolExecutor,
        usessl: bool = False,
    )
    """
    logger = get_logger_from_config(config)

    if executor is None:
        executor = ThreadPoolExecutor(max_workers=10)

    return MinIOConnector(
        endpoint=config.minio.endpoint,
        access_key=config.minio.access_key,
        secret_key=config.minio.secret_key,
        bucket=config.minio.bucket_name,
        get_logger=lambda: logger,
        executor=executor,
        use_ssl=config.minio.use_ssl,
    )


def _create_db_connector(
    config: Settings,
) -> PGConnector:
    """
    Создать PostgreSQL-коннектор из Settings (config.postgres).
    Сигнатура PGConnector.__init__:

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        minpoolsize: int = 1,
        maxpoolsize: int = 20,
        logger: Optional[logging.Logger] = None,
    )
    """
    logger = get_logger_from_config(config)

    return PGConnector(
        host=config.postgres.host,
        port=config.postgres.port,
        database=config.postgres.database,
        user=config.postgres.user,
        password=config.postgres.password,
        min_pool_size=config.postgres.pool_min_size,
        max_pool_size=config.postgres.pool_max_size,
        logger=logger,
    )


def _create_http_connector(
    config: Settings,
    health_callback: Optional[Callable[[], Awaitable[dict]]] = None,
    status_callback: Optional[Callable[[], Awaitable[dict]]] = None,
) -> FastApiConnector:
    logger = get_logger_from_config(config)

    return FastApiConnector(
        host=config.http.host,
        port=config.http.port,
        get_logger=lambda: logger,
        health_callback=health_callback,
        status_callback=status_callback,
    )


def create_all_interfaces(
    config: Optional[Settings] = None,
    event_publisher: Optional[EventPublisher] = None,
    executor: Optional[ThreadPoolExecutor] = None,
) -> Dict[str, Any]:
    """
    Create all available interfaces using the default factory.

    Args:
        config: Optional settings instance (uses get_settings() if None)
        event_publisher: Optional event publisher for observability
        executor: Optional thread pool executor

    Returns:
        Dictionary mapping interface names to interface instances
    """
    cfg = config or get_settings()
    factory = InterfaceFactory(cfg)
    return factory.create_all_interfaces(
        event_publisher=event_publisher,
        executor=executor,
    )
