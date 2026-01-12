"""
Configuration module using Pydantic Settings.

Reads from .env file and environment variables.
All fields are optional with sensible defaults.

Structure is flat - backwards compatible with existing code.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Main application settings - flat structure for backwards compatibility"""
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"  # Ignore extra fields
    )

    # ========================================================================
    # LOGGING
    # ========================================================================
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format: json or text")
    log_enable_debug: bool = Field(default=False, description="Enable debug logging")
    log_file: Optional[str] = Field(default=None, description="Log file path")

    # ========================================================================
    # GIGACHAT / LLM
    # ========================================================================
    gigachat_access_token: Optional[str] = Field(default=None, description="GigaChat access token")
    gigachat_model: str = Field(default="GigaChat-Max", description="Model name")
    gigachat_scope: str = Field(default="GIGACHAT_API_B2B", description="API scope")
    gigachat_verify_ssl: bool = Field(default=False, description="Verify SSL certificates")
    gigachat_request_timeout_seconds: int = Field(default=30, description="Request timeout")
    gigachat_max_connections: int = Field(default=100, description="Max connections")
    gigachat_base_url: str = Field(
        default="https://gigachat.devices.sberbank.ru",
        description="Base URL"
    )
    gigachat_api_version: str = Field(
        default="api/v1",
        description="API version"
    )
    gigachat_oauth_url: str = Field(default="https://ngw.devices.sberbank.ru:9443/api/v2/oauth", description="OAuth URL")

    # ========================================================================
    # KAFKA
    # ========================================================================
    kafka_bootstrap_servers: str = Field(
        default="localhost:9092",
        description="Kafka bootstrap servers"
    )
    kafka_group_id: str = Field(
        default="llm-worker-group",
        description="Consumer group ID"
    )
    kafka_auto_offset_reset: str = Field(
        default="earliest",
        description="Auto offset reset policy"
    )
    kafka_consumer_poll_timeout: float = Field(
        default=1.0,
        description="Consumer poll timeout"
    )

    # ========================================================================
    # MINIO
    # ========================================================================
    minio_endpoint: str = Field(
        default="localhost:9000",
        description="MinIO endpoint"
    )
    minio_access_key: str = Field(
        default="minioadmin",
        description="MinIO access key"
    )
    minio_secret_key: str = Field(
        default="minioadmin",
        description="MinIO secret key"
    )
    minio_bucket_name: str = Field(
        default="documents",
        description="Bucket name"
    )
    minio_use_ssl: bool = Field(
        default=False,
        description="Use SSL"
    )
    minio_enabled: bool = Field(
        default=True,
        description="Enable MinIO"
    )

    # ========================================================================
    # POSTGRESQL
    # ========================================================================
    postgres_host: str = Field(
        default="localhost",
        description="Database host"
    )
    postgres_port: int = Field(
        default=5432,
        description="Database port"
    )
    postgres_database: str = Field(
        default="worker_db",
        description="Database name"
    )
    postgres_user: str = Field(
        default="postgres",
        description="Database user"
    )
    postgres_password: str = Field(
        default="postgres",
        description="Database password"
    )
    postgres_pool_min_size: int = Field(
        default=1,
        description="Pool min size"
    )
    postgres_pool_max_size: int = Field(
        default=20,
        description="Pool max size"
    )
    postgres_enabled: bool = Field(
        default=True,
        description="Enable PostgreSQL"
    )

    # ========================================================================
    # WORKER CONFIGURATION
    # ========================================================================
    worker_max_concurrent_tasks: int = Field(
        default=10,
        description="Max concurrent tasks"
    )
    executor_max_workers: int = Field(
        default=20,
        description="Max executor workers"
    )

    # Circuit breaker
    circuit_breaker_failure_threshold: int = Field(
        default=5,
        description="Failure threshold"
    )
    circuit_breaker_timeout_sec: float = Field(
        default=30.0,
        description="Timeout in seconds"
    )

    # Retry settings
    llm_max_retries: int = Field(
        default=3,
        description="Max retries"
    )
    llm_retry_initial_delay: float = Field(
        default=2.0,
        description="Initial delay"
    )
    llm_retry_max_delay: float = Field(
        default=10.0,
        description="Max delay"
    )
    python_gil_enabled: bool = Field(
        default=False,
        description="Enable GIL"
    )

    # ========================================================================
    # HELPER PROPERTIES
    # ========================================================================

    @property
    def postgres_dsn(self) -> str:
        """PostgreSQL connection string"""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_database}"
        )

    @property
    def kafka(self):
        """Kafka config object (for backwards compatibility)"""
        class KafkaConfig:
            def __init__(self, settings):
                self.bootstrap_servers = settings.kafka_bootstrap_servers
                self.group_id = settings.kafka_group_id
                self.auto_offset_reset = settings.kafka_auto_offset_reset
                self.consumer_poll_timeout = settings.kafka_consumer_poll_timeout

        return KafkaConfig(self)

    @property
    def gigachat(self):
        """GigaChat config object (for backwards compatibility)"""
        class GigaChatConfig:
            def __init__(self, settings):
                self.access_token = settings.gigachat_access_token
                self.model = settings.gigachat_model
                self.scope = settings.gigachat_scope
                self.verify_ssl = settings.gigachat_verify_ssl
                self.request_timeout_seconds = settings.gigachat_request_timeout_seconds
                self.max_connections = settings.gigachat_max_connections
                self.base_url = settings.gigachat_base_url
                self.api_version = settings.gigachat_api_version
                self.oauth_url = settings.gigachat_oauth_url

        return GigaChatConfig(self)

    @property
    def minio(self):
        """MinIO config object (for backwards compatibility)"""
        class MinIOConfig:
            def __init__(self, settings):
                self.endpoint = settings.minio_endpoint
                self.access_key = settings.minio_access_key
                self.secret_key = settings.minio_secret_key
                self.bucket_name = settings.minio_bucket_name
                self.use_ssl = settings.minio_use_ssl
                self.enabled = settings.minio_enabled

        return MinIOConfig(self)

    @property
    def postgres(self):
        """PostgreSQL config object (for backwards compatibility)"""
        class PostgresConfig:
            def __init__(self, settings):
                self.host = settings.postgres_host
                self.port = settings.postgres_port
                self.database = settings.postgres_database
                self.user = settings.postgres_user
                self.password = settings.postgres_password
                self.pool_min_size = settings.postgres_pool_min_size
                self.pool_max_size = settings.postgres_pool_max_size
                self.enabled = settings.postgres_enabled

        return PostgresConfig(self)


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Get global settings instance (singleton)"""
    global _settings_instance

    if _settings_instance is None:
        _settings_instance = Settings()

    return _settings_instance


def reset_settings() -> None:
    """Reset settings instance (for testing)"""
    global _settings_instance
    _settings_instance = None


# ============================================================================
# DEBUG HELPER
# ============================================================================

def print_settings() -> None:
    """Print current settings (for debugging)"""
    settings = get_settings()
    print("\n" + "="*70)
    print("CURRENT SETTINGS")
    print("="*70)
    print(f"Log Level: {settings.log_level}")
    print(f"Log Format: {settings.log_format}")
    print(f"Log Debug: {settings.log_enable_debug}")
    print(f"Log File: {settings.log_file or 'stdout'}")
    print(f"\nGigaChat:")
    print(f"  Model: {settings.gigachat_model}")
    print(f"\nKafka:")
    print(f"  Bootstrap: {settings.kafka_bootstrap_servers}")
    print(f"  Group: {settings.kafka_group_id}")
    print(f"\nMinIO:")
    print(f"  Endpoint: {settings.minio_endpoint}")
    print(f"  Bucket: {settings.minio_bucket_name}")
    print(f"\nPostgreSQL:")
    print(f"  Host: {settings.postgres_host}:{settings.postgres_port}")
    print(f"  Database: {settings.postgres_database}")
    print(f"\nWorker:")
    print(f"  Max Concurrent: {settings.worker_max_concurrent_tasks}")
    print(f"  Max Retries: {settings.llm_max_retries}")
    print("="*70 + "\n")