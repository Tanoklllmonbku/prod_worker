from concurrent.futures import ThreadPoolExecutor
from typing import Any, Awaitable, Callable, Dict, Optional

from config.config import Settings, get_settings
from connectors.gigachat_connector import GigaChatConnector
from connectors.kafka_connector import KafkaConnector
from connectors.minio_connector import MinIOConnector
from connectors.pg_connector import PGConnector
from connectors.http_connector import FastApiConnector  
from interface.db import DBInterface
from interface.llm import LLMInterface
from interface.queue import QueueInterface
from interface.storage import StorageInterface
from interface.http import HTTPInterface
from utils.logging import get_logger_from_config
from utils.observer import EventPublisher


class ConnectorRegistryFactory:
    """Special naming constructor for connectors"""

    def __init__(self, config: Settings):
        self.config: Settings = config
from core.base_class.base_interface import BaseInterface


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


def create_llm_interface(
    config: Optional[Settings] = None,
    name: str = "GigaChat",
    event_publisher: Optional[EventPublisher] = None,
) -> LLMInterface:
    cfg = config or get_settings()
    worker = _create_llm_connector(cfg)
    return LLMInterface(worker=worker, name=name, event_publisher=event_publisher)


def create_queue_interface(
    config: Optional[Settings] = None,
    name: str = "Kafka",
    event_publisher: Optional[EventPublisher] = None,
) -> QueueInterface:
    cfg = config or get_settings()
    worker = _create_queue_connector(cfg)
    return QueueInterface(worker=worker, name=name, event_publisher=event_publisher)


def create_storage_interface(
    config: Optional[Settings] = None,
    name: str = "Minio",  # ← Исправлено имя по умолчанию
    event_publisher: Optional[EventPublisher] = None,
    executor: Optional[ThreadPoolExecutor] = None,
) -> StorageInterface:
    cfg = config or get_settings()
    worker = _create_storage_connector(cfg, executor=executor)
    return StorageInterface(worker=worker, name=name, event_publisher=event_publisher)


def create_db_interface(
    config: Optional[Settings] = None,
    name: str = "Postgres",
    event_publisher: Optional[EventPublisher] = None,
) -> DBInterface:
    cfg = config or get_settings()
    worker = _create_db_connector(cfg)
    return DBInterface(worker=worker, name=name, event_publisher=event_publisher)


def create_http_interface(
    config: Optional[Settings] = None,
    name: str = "FastApi",
    event_publisher: Optional[EventPublisher] = None,
    health_callback: Optional[Callable[[], Awaitable[dict]]] = None,
    status_callback: Optional[Callable[[], Awaitable[dict]]] = None,
) -> HTTPInterface:
    cfg = config or get_settings()
    worker = _create_http_connector(
        cfg,
        health_callback=health_callback,
        status_callback=status_callback
    )
    return HTTPInterface(worker=worker, name=name, event_publisher=event_publisher)


def create_all_interfaces(
    config: Optional[Settings] = None,
    event_publisher: Optional[EventPublisher] = None,
    executor: Optional[ThreadPoolExecutor] = None,
) -> Dict[str, Any]:
    cfg = config or get_settings()
    interfaces: Dict[str, Any] = {}

    interfaces["GigaChat"] = create_llm_interface(
        cfg, event_publisher=event_publisher
    )

    if cfg.kafka.bootstrap_servers:
        interfaces["Kafka"] = create_queue_interface(
            cfg, event_publisher=event_publisher
        )

    if cfg.minio.enabled:
        interfaces["Minio"] = create_storage_interface(
            cfg, event_publisher=event_publisher, executor=executor
        )

    if cfg.postgres.enabled:
        interfaces["Postgres"] = create_db_interface(
            cfg, event_publisher=event_publisher
        )

    # === ДОБАВЛЕНО HTTP ===
    if cfg.http.enabled:  # Предполагается, что в конфиге есть флаг enabled
        interfaces["FastApi"] = create_http_interface(
            cfg, event_publisher=event_publisher
        )

    return interfaces
