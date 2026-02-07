"""
HTTP Server Configuration Module
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class HttpSettings(BaseSettings):
    """HTTP server configuration settings"""
    enabled: bool = Field(
        default=True,
        description="Enable HTTP monitoring server"
    )
    host: str = Field(
        default="127.0.0.1",
        description="Host for HTTP server (Default - localhost)"
    )
    port: int = Field(
        default=8000,
        description="Port for HTTP server (Default - 8000)"
    )

    class Config:
        env_prefix = "HTTP_"