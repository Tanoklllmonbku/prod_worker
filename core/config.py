"""
Core configuration module with JSON file support.

Supports loading configuration from:
1. JSON file (config/config.json)
2. Environment variables (override JSON values)
3. Keyring for sensitive data (auth keys, passwords)
"""
import os
import json
from pathlib import Path
from typing import List, Optional, Dict, Any

import keyring
from pydantic_settings import BaseSettings

from core.connector_configs import (
    ConnectorsConfig,
    load_connectors_config,
    LLMConnectorConfig,
    DBConnectorConfig,
    QueueConnectorConfig,
    StorageConnectorConfig,
)


class Config(BaseSettings):
    """Application configuration with JSON file and env var support"""

    # Config file path
    config_file: Optional[str] = os.getenv("CONFIG_FILE", "config/config.json")

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file: str = os.getenv("LOG_FILE", "logs/system.log")
    log_enable_debug: bool = os.getenv("LOG_ENABLE_DEBUG", "false").lower() == "true"

    # API
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    api_workers: int = int(os.getenv("API_WORKERS", "4"))
    api_log_level: str = os.getenv("API_LOG_LEVEL", "INFO")
    api_timeout: int = int(os.getenv("API_TIMEOUT", "30"))
    api_cors_origins: List[str] = ["*"]

    # Feature flags
    enable_minio: bool = os.getenv("ENABLE_MINIO", "true").lower() == "true"
    enable_database: bool = os.getenv("ENABLE_DATABASE", "true").lower() == "true"
    enable_kafka: bool = os.getenv("ENABLE_KAFKA", "true").lower() == "true"

    # Connectors config
    connectors_config: Optional[ConnectorsConfig] = None

    # Legacy support (backward compatibility)
    # These are populated from connectors_config or env vars
    @property
    def gigachat_token(self) -> str:
        """Get GigaChat token from keyring"""
        token = keyring.get_password("myapp", "gigachat_token")
        if not token:
            raise ValueError(
                "GigaChat token not found in keyring. Set it first with: "
                "keyring.set_password('myapp', 'gigachat_token', 'your_token')"
            )
        return token

    @property
    def gigachat_model(self) -> str:
        """Get GigaChat model from connectors config or env"""
        if self.connectors_config and self.connectors_config.llm:
            return self.connectors_config.llm.model
        return os.getenv("GIGACHAT_MODEL", "GigaChat-Max")

    @property
    def gigachat_scope(self) -> str:
        """Get GigaChat scope from connectors config or env"""
        if self.connectors_config and self.connectors_config.llm:
            return self.connectors_config.llm.scope
        return os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_B2B")

    # MinIO (legacy)
    @property
    def minio_endpoint(self) -> str:
        if self.connectors_config and self.connectors_config.storage:
            return self.connectors_config.storage.endpoint
        return os.getenv("MINIO_ENDPOINT", "localhost:9000")

    @property
    def minio_access_key(self) -> str:
        if self.connectors_config and self.connectors_config.storage:
            return self.connectors_config.storage.access_key
        return os.getenv("MINIO_ACCESS_KEY", "minioadmin")

    @property
    def minio_secret_key(self) -> str:
        if self.connectors_config and self.connectors_config.storage:
            return self.connectors_config.storage.secret_key
        return os.getenv("MINIO_SECRET_KEY", "minioadmin")

    @property
    def minio_bucket(self) -> str:
        if self.connectors_config and self.connectors_config.storage:
            return self.connectors_config.storage.bucket
        return os.getenv("MINIO_BUCKET", "gigachat-files")

    @property
    def minio_use_ssl(self) -> bool:
        if self.connectors_config and self.connectors_config.storage:
            return self.connectors_config.storage.use_ssl
        return os.getenv("MINIO_USE_SSL", "false").lower() == "true"

    # Database (legacy)
    @property
    def db_type(self) -> str:
        return os.getenv("DB_TYPE", "postgresql")

    @property
    def db_host(self) -> str:
        if self.connectors_config and self.connectors_config.db:
            return self.connectors_config.db.host
        return os.getenv("DB_HOST", "localhost")

    @property
    def db_port(self) -> int:
        if self.connectors_config and self.connectors_config.db:
            return self.connectors_config.db.port
        return int(os.getenv("DB_PORT", "5432"))

    @property
    def db_name(self) -> str:
        if self.connectors_config and self.connectors_config.db:
            return self.connectors_config.db.database
        return os.getenv("DB_NAME", "gigachat_db")

    @property
    def db_user(self) -> str:
        if self.connectors_config and self.connectors_config.db:
            return self.connectors_config.db.user
        return os.getenv("DB_USER", "postgres")

    @property
    def db_password(self) -> str:
        if self.connectors_config and self.connectors_config.db:
            return self.connectors_config.db.password
        return os.getenv("DB_PASSWORD", "password")

    @property
    def db_pool_size(self) -> int:
        if self.connectors_config and self.connectors_config.db:
            return self.connectors_config.db.min_pool_size
        return int(os.getenv("DB_POOL_SIZE", "10"))

    @property
    def db_max_overflow(self) -> int:
        if self.connectors_config and self.connectors_config.db:
            return self.connectors_config.db.max_pool_size
        return int(os.getenv("DB_MAX_OVERFLOW", "20"))

    # Kafka (legacy)
    @property
    def kafka_bootstrap_servers(self) -> str:
        if self.connectors_config and self.connectors_config.queue:
            return ",".join(self.connectors_config.queue.bootstrap_servers)
        return os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    @property
    def kafka_topic_default(self) -> str:
        return os.getenv("KAFKA_TOPIC_DEFAULT", "gigachat-events")

    @property
    def kafka_consumer_group(self) -> str:
        if self.connectors_config and self.connectors_config.queue:
            return self.connectors_config.queue.consumer_group or "gigachat-consumer"
        return os.getenv("KAFKA_CONSUMER_GROUP", "gigachat-consumer")

    @property
    def kafka_auto_offset_reset(self) -> str:
        if self.connectors_config and self.connectors_config.queue:
            return self.connectors_config.queue.auto_offset_reset
        return os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest")

    def __init__(self, **kwargs):
        """Initialize config with JSON file loading"""
        # Load connectors config from JSON file
        config_file = kwargs.get("config_file") or os.getenv("CONFIG_FILE", "config/config.json")
        config_path = Path(config_file)

        # Try to load from JSON file
        json_data = {}
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    json_data = json.load(f)
            except Exception:
                pass  # Use defaults if file can't be loaded

        # Override with env vars or kwargs
        if "log_level" not in kwargs and "LOG_LEVEL" not in os.environ:
            kwargs["log_level"] = json_data.get("logging", {}).get("level", "INFO")
        if "log_file" not in kwargs and "LOG_FILE" not in os.environ:
            kwargs["log_file"] = json_data.get("logging", {}).get("file", "logs/system.log")
        if "log_enable_debug" not in kwargs and "LOG_ENABLE_DEBUG" not in os.environ:
            kwargs["log_enable_debug"] = json_data.get("logging", {}).get("enable_debug", False)

        if "api_host" not in kwargs and "API_HOST" not in os.environ:
            kwargs["api_host"] = json_data.get("api", {}).get("host", "0.0.0.0")
        if "api_port" not in kwargs and "API_PORT" not in os.environ:
            kwargs["api_port"] = json_data.get("api", {}).get("port", 8000)

        if "enable_minio" not in kwargs and "ENABLE_MINIO" not in os.environ:
            kwargs["enable_minio"] = json_data.get("features", {}).get("enable_minio", True)
        if "enable_database" not in kwargs and "ENABLE_DATABASE" not in os.environ:
            kwargs["enable_database"] = json_data.get("features", {}).get("enable_database", True)
        if "enable_kafka" not in kwargs and "ENABLE_KAFKA" not in os.environ:
            kwargs["enable_kafka"] = json_data.get("features", {}).get("enable_kafka", True)

        super().__init__(**kwargs)

        # Load connectors config
        try:
            connectors_data = json_data.get("connectors", {})
            if connectors_data:
                self.connectors_config = ConnectorsConfig.from_dict(connectors_data)
            else:
                # Try separate connectors.json file
                self.connectors_config = load_connectors_config()
        except Exception:
            # Use defaults if loading fails
            self.connectors_config = None

    class Config:
        env_file = ".env"
        case_sensitive = False


_config: Optional[Config] = None


def get_config(config_file: Optional[str] = None) -> Config:
    """Get singleton config instance"""
    global _config
    if _config is None:
        kwargs = {}
        if config_file:
            kwargs["config_file"] = config_file
        _config = Config(**kwargs)
    return _config


def reload_config(config_file: Optional[str] = None) -> Config:
    """Reload configuration from file/environment"""
    global _config
    kwargs = {}
    if config_file:
        kwargs["config_file"] = config_file
    _config = Config(**kwargs)
    return _config
