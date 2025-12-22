"""
Connector configuration classes.

Provides typed configuration classes for each connector type with validation.
All configurations can be loaded from JSON files.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path
import json


@dataclass
class CommonConnectorConfig:
    """Common configuration parameters for all connectors"""

    timeout: float = 30.0
    connection_timeout: float = 10.0
    retry_count: int = 3
    retry_delay: float = 1.0
    health_check_interval: float = 60.0


@dataclass
class LLMConnectorConfig(CommonConnectorConfig):
    """Configuration for LLM connectors (GigaChat, etc.)"""

    model: str = "GigaChat-Max"
    scope: str = "GIGACHAT_API_B2B"
    verify_ssl: bool = False
    max_connections: int = 100
    auth_key: Optional[str] = None
    access_token: Optional[str] = None


@dataclass
class DBConnectorConfig(CommonConnectorConfig):
    """Configuration for database connectors (PostgreSQL, etc.)"""

    host: str = "localhost"
    port: int = 5432
    database: str = "gigachat_db"
    user: str = "postgres"
    password: str = "password"
    min_pool_size: int = 1
    max_pool_size: int = 20


@dataclass
class QueueConnectorConfig(CommonConnectorConfig):
    """Configuration for queue connectors (Kafka, etc.)"""

    bootstrap_servers: List[str] = field(default_factory=lambda: ["localhost:9092"])
    default_format: str = "json"  # json, msgpack
    consumer_poll_timeout: float = 1.0
    auto_offset_reset: str = "earliest"
    consumer_group: Optional[str] = None


@dataclass
class StorageConnectorConfig(CommonConnectorConfig):
    """Configuration for storage connectors (MinIO, S3, etc.)"""

    endpoint: str = "localhost:9000"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    bucket: str = "gigachat-files"
    use_ssl: bool = False
    region: Optional[str] = None


@dataclass
class ConnectorsConfig:
    """Complete connectors configuration"""

    llm: Optional[LLMConnectorConfig] = None
    db: Optional[DBConnectorConfig] = None
    queue: Optional[QueueConnectorConfig] = None
    storage: Optional[StorageConnectorConfig] = None

    @classmethod
    def from_dict(cls, data: dict) -> ConnectorsConfig:
        """Create config from dictionary"""
        config = cls()

        if "llm" in data:
            config.llm = LLMConnectorConfig(**data["llm"])

        if "db" in data:
            config.db = DBConnectorConfig(**data["db"])

        if "queue" in data:
            queue_data = data["queue"].copy()
            # Handle bootstrap_servers as string or list
            if "bootstrap_servers" in queue_data:
                if isinstance(queue_data["bootstrap_servers"], str):
                    queue_data["bootstrap_servers"] = [
                        s.strip()
                        for s in queue_data["bootstrap_servers"].split(",")
                    ]
            config.queue = QueueConnectorConfig(**queue_data)

        if "storage" in data:
            config.storage = StorageConnectorConfig(**data["storage"])

        return config

    @classmethod
    def from_json_file(cls, path: str | Path) -> ConnectorsConfig:
        """Load configuration from JSON file"""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls.from_dict(data.get("connectors", {}))

    def to_dict(self) -> dict:
        """Convert config to dictionary"""
        result = {}
        if self.llm:
            result["llm"] = self._dataclass_to_dict(self.llm)
        if self.db:
            result["db"] = self._dataclass_to_dict(self.db)
        if self.queue:
            result["queue"] = self._dataclass_to_dict(self.queue)
        if self.storage:
            result["storage"] = self._dataclass_to_dict(self.storage)
        return result

    @staticmethod
    def _dataclass_to_dict(obj) -> dict:
        """Convert dataclass to dict"""
        from dataclasses import fields, asdict

        return asdict(obj)


def load_connectors_config(
    config_path: Optional[str | Path] = None,
) -> ConnectorsConfig:
    """
    Load connectors configuration from JSON file.

    Args:
        config_path: Path to config file (default: config/connectors.json)

    Returns:
        ConnectorsConfig instance
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "connectors.json"

    try:
        return ConnectorsConfig.from_json_file(config_path)
    except FileNotFoundError:
        # Return default config if file doesn't exist
        return ConnectorsConfig()

