from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from config.config import Settings, get_settings
from connectors.gigachat_connector_new import GigaChatConnector as NewGigaChatConnector
from connectors.kafka_connector_new import KafkaConnector as NewKafkaConnector
from connectors.minio_connector import MinIOConnector
from connectors.pg_connector import PGConnector
from interface.db import DBInterface
from interface.llm import LLMInterface
from interface.queue import QueueInterface
from interface.storage import StorageInterface
from utils.logging import get_logger_from_config
from utils.observer import EventPublisher


def _create_new_llm_connector(
    config: Settings,
) -> NewGigaChatConnector:
    """
    Создать новый GigaChat-коннектор из Settings (config.gigachat).
    """
    logger = get_logger_from_config(config)

    return NewGigaChatConnector(
        get_logger=lambda: logger,
        credentials=config.gigachat_access_token,
        model=config.gigachat.model,
        scope=config.gigachat.scope,
        verify_ssl=config.gigachat.verify_ssl,
        timeout=float(config.gigachat.request_timeout_seconds),
        max_connections=config.gigachat.max_connections,
        base_url=config.gigachat.base_url,
        api_version=config.gigachat.api_version,
        oauth_url=config.gigachat_oauth_url,
    )


def _create_new_queue_connector(
    config: Settings,
) -> NewKafkaConnector:
    """
    Создать новый Kafka-коннектор из Settings (config.kafka).
    """
    logger = get_logger_from_config(config)

    servers_raw = config.kafka.bootstrap_servers
    if isinstance(servers_raw, str):
        bootstrap_servers = [s.strip() for s in servers_raw.split(",") if s.strip()]
    else:
        bootstrap_servers = list(servers_raw)

    return NewKafkaConnector(
        bootstrap_servers=bootstrap_servers,
        group_id=config.kafka.group_id,
        logger=logger,
        consumer_poll_timeout=config.kafka.consumer_poll_timeout,
    )


def create_new_llm_interface(
    config: Optional[Settings] = None,
    name: str = "GigaChat",
    event_publisher: Optional[EventPublisher] = None,
) -> LLMInterface:
    cfg = config or get_settings()
    worker = _create_new_llm_connector(cfg)
    return LLMInterface(worker=worker, name=name, event_publisher=event_publisher)


def create_new_queue_interface(
    config: Optional[Settings] = None,
    name: str = "Kafka",
    event_publisher: Optional[EventPublisher] = None,
) -> QueueInterface:
    cfg = config or get_settings()
    worker = _create_new_queue_connector(cfg)
    return QueueInterface(worker=worker, name=name, event_publisher=event_publisher)


def create_all_new_interfaces(
    config: Optional[Settings] = None,
    event_publisher: Optional[EventPublisher] = None,
) -> Dict[str, Any]:
    cfg = config or get_settings()
    interfaces: Dict[str, Any] = {}

    interfaces["NewGigaChat"] = create_new_llm_interface(
        cfg, event_publisher=event_publisher
    )

    if cfg.kafka.bootstrap_servers:
        interfaces["NewKafka"] = create_new_queue_interface(
            cfg, event_publisher=event_publisher
        )

    # Keep the original connectors for comparison
    from core.factories import create_all_interfaces
    original_interfaces = create_all_interfaces(config=cfg, event_publisher=event_publisher)
    
    # Merge with original interfaces
    interfaces.update({k: v for k, v in original_interfaces.items() if k not in interfaces})

    return interfaces