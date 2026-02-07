"""
Worker Configuration Module
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class WorkerSettings(BaseSettings):
    """Worker configuration settings"""
    max_concurrent_tasks: int = Field(
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
    max_retries: int = Field(
        default=3,
        description="Max retries"
    )
    retry_initial_delay: float = Field(
        default=2.0,
        description="Initial delay"
    )
    retry_max_delay: float = Field(
        default=10.0,
        description="Max delay"
    )
    python_gil_enabled: bool = Field(
        default=False,
        description="Enable GIL"
    )

    class Config:
        env_prefix = "WORKER_"