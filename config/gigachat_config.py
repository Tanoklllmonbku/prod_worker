"""
GigaChat Configuration Module
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class GigaChatSettings(BaseSettings):
    """GigaChat configuration settings"""
    access_token: Optional[str] = Field(default=None, description="GigaChat access token")
    model: str = Field(default="GigaChat-Max", description="Model name")
    scope: str = Field(default="GIGACHAT_API_B2B", description="API scope")
    verify_ssl: bool = Field(default=False, description="Verify SSL certificates")
    request_timeout_seconds: int = Field(default=30, description="Request timeout")
    max_connections: int = Field(default=100, description="Max connections")
    base_url: str = Field(
        default="https://gigachat.devices.sberbank.ru",
        description="Base URL"
    )
    api_version: str = Field(
        default="api/v1",
        description="API version"
    )
    oauth_url: str = Field(default="https://ngw.devices.sberbank.ru:9443/api/v2/oauth", description="OAuth URL")

    class Config:
        env_prefix = "GIGACHAT_"