"""
Main Configuration Module - Modular Configuration System

This module provides a modular configuration system with separate settings
for each subsystem of the application.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

from .logging_config import LoggingSettings
from .gigachat_config import GigaChatSettings
from .kafka_config import KafkaSettings
from .minio_config import MinIOSettings
from .postgres_config import PostgreSettings
from .http_config import HttpSettings
from .worker_config import WorkerSettings


class Settings(BaseSettings):
    """Main application settings - modular structure"""
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"  # Ignore extra fields
    )

    # Include all subsystem configurations
    logging: LoggingSettings = LoggingSettings()
    gigachat: GigaChatSettings = GigaChatSettings()
    kafka: KafkaSettings = KafkaSettings()
    minio: MinIOSettings = MinIOSettings()
    postgres: PostgreSettings = PostgreSettings()
    http: HttpSettings = HttpSettings()
    worker: WorkerSettings = WorkerSettings()

    # Backwards compatibility properties
    @property
    def log_level(self) -> str:
        return self.logging.log_level

    @property
    def log_format(self) -> str:
        return self.logging.log_format

    @property
    def log_enable_debug(self) -> bool:
        return self.logging.log_enable_debug

    @property
    def log_file(self) -> Optional[str]:
        return self.logging.log_file

    # GigaChat backwards compatibility
    @property
    def gigachat_access_token(self) -> Optional[str]:
        return self.gigachat.access_token

    @property
    def gigachat_model(self) -> str:
        return self.gigachat.model

    @property
    def gigachat_scope(self) -> str:
        return self.gigachat.scope

    @property
    def gigachat_verify_ssl(self) -> bool:
        return self.gigachat.verify_ssl

    @property
    def gigachat_request_timeout_seconds(self) -> int:
        return self.gigachat.request_timeout_seconds

    @property
    def gigachat_max_connections(self) -> int:
        return self.gigachat.max_connections

    @property
    def gigachat_base_url(self) -> str:
        return self.gigachat.base_url

    @property
    def gigachat_api_version(self) -> str:
        return self.gigachat.api_version

    @property
    def gigachat_oauth_url(self) -> str:
        return self.gigachat.oauth_url

    # Kafka backwards compatibility
    @property
    def kafka_bootstrap_servers(self) -> str:
        return self.kafka.bootstrap_servers

    @property
    def kafka_group_id(self) -> str:
        return self.kafka.group_id

    @property
    def kafka_auto_offset_reset(self) -> str:
        return self.kafka.auto_offset_reset

    @property
    def kafka_consumer_poll_timeout(self) -> float:
        return self.kafka.consumer_poll_timeout

    # MinIO backwards compatibility
    @property
    def minio_endpoint(self) -> str:
        return self.minio.endpoint

    @property
    def minio_access_key(self) -> str:
        return self.minio.access_key

    @property
    def minio_secret_key(self) -> str:
        return self.minio.secret_key

    @property
    def minio_bucket_name(self) -> str:
        return self.minio.bucket_name

    @property
    def minio_use_ssl(self) -> bool:
        return self.minio.use_ssl

    @property
    def minio_enabled(self) -> bool:
        return self.minio.enabled

    # PostgreSQL backwards compatibility
    @property
    def postgres_host(self) -> str:
        return self.postgres.host

    @property
    def postgres_port(self) -> int:
        return self.postgres.port

    @property
    def postgres_database(self) -> str:
        return self.postgres.database

    @property
    def postgres_user(self) -> str:
        return self.postgres.user

    @property
    def postgres_password(self) -> str:
        return self.postgres.password

    @property
    def postgres_pool_min_size(self) -> int:
        return self.postgres.pool_min_size

    @property
    def postgres_pool_max_size(self) -> int:
        return self.postgres.pool_max_size

    @property
    def postgres_dsn(self) -> str:
        return self.postgres.dsn

    # HTTP backwards compatibility
    @property
    def http_enabled(self) -> bool:
        return self.http.enabled

    @property
    def http_ip(self) -> str:
        return self.http.host

    @property
    def http_port(self) -> int:
        return self.http.port

    # Worker backwards compatibility
    @property
    def worker_max_concurrent_tasks(self) -> int:
        return self.worker.max_concurrent_tasks

    @property
    def executor_max_workers(self) -> int:
        return self.worker.executor_max_workers

    @property
    def circuit_breaker_failure_threshold(self) -> int:
        return self.worker.circuit_breaker_failure_threshold

    @property
    def circuit_breaker_timeout_sec(self) -> float:
        return self.worker.circuit_breaker_timeout_sec

    @property
    def llm_max_retries(self) -> int:
        return self.worker.max_retries

    @property
    def llm_retry_initial_delay(self) -> float:
        return self.worker.retry_initial_delay

    @property
    def llm_retry_max_delay(self) -> float:
        return self.worker.retry_max_delay

    @property
    def python_gil_enabled(self) -> bool:
        return self.worker.python_gil_enabled


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