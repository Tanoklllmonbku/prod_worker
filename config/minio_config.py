"""
MinIO Configuration Module
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class MinIOSettings(BaseSettings):
    """MinIO configuration settings"""
    endpoint: str = Field(
        default="localhost:9000",
        description="MinIO endpoint"
    )
    access_key: str = Field(
        default="minioadmin",
        description="MinIO access key"
    )
    secret_key: str = Field(
        default="minioadmin",
        description="MinIO secret key"
    )
    bucket_name: str = Field(
        default="documents",
        description="Bucket name"
    )
    use_ssl: bool = Field(
        default=False,
        description="Use SSL"
    )
    enabled: bool = Field(
        default=True,
        description="Enable MinIO"
    )

    class Config:
        env_prefix = "MINIO_"