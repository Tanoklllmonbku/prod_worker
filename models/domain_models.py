"""
Domain Data Models - Centralized imports for domain-specific data models.

This module provides convenient access to all domain-specific data models.
"""

# Export domain-specific models
from .kafka_model import TaskStatus, KafkaMessage, KafkaKey, KafkaHeaders, KafkaValueConsumer, KafkaValueProducer
from .http_model import HealthResponse, StatusResponse
from .prompt_model import Prompt, PromptService, DO1, DO3
from .db_model import DBLogEvent, DBLogEntry
from .minio_model import MinIORequest, MinIOResponse

__all__ = [
    # Kafka models
    'TaskStatus',
    'KafkaMessage',
    'KafkaKey',
    'KafkaHeaders',
    'KafkaValueConsumer',
    'KafkaValueProducer',
    
    # HTTP models
    'HealthResponse',
    'StatusResponse',
    
    # Prompt models
    'Prompt',
    'PromptService',
    'DO1',
    'DO3',
    
    # Database models
    'DBLogEvent',
    'DBLogEntry',
    
    # MinIO models
    'MinIORequest',
    'MinIOResponse',
]