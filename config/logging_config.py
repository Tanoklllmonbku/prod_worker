"""
Logging Configuration Module
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class LoggingSettings(BaseSettings):
    """Logging configuration settings"""
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format: json or text")
    log_enable_debug: bool = Field(default=False, description="Enable debug logging")
    log_file: Optional[str] = Field(default=None, description="Log file path")

    class Config:
        env_prefix = "LOG_"