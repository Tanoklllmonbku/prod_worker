"""
Пример конфигурации для подключения к PostgreSQL
"""

import os
from typing import Optional


class PostgresConfig:
    """
    Конфигурация для подключения к PostgreSQL
    """
    
    def __init__(self):
        # Базовые параметры подключения
        self.host: str = os.getenv('POSTGRES_HOST', 'localhost')
        self.port: int = int(os.getenv('POSTGRES_PORT', 5432))
        self.database: str = os.getenv('POSTGRES_DB', 'postgres')
        self.user: str = os.getenv('POSTGRES_USER', 'postgres')
        self.password: str = os.getenv('POSTGRES_PASSWORD', 'postgres')
        
        # Параметры пула соединений
        self.min_pool_size: int = int(os.getenv('POSTGRES_MIN_POOL_SIZE', 1))
        self.max_pool_size: int = int(os.getenv('POSTGRES_MAX_POOL_SIZE', 20))
        
        # Параметры SSL (опционально)
        self.ssl_mode: str = os.getenv('POSTGRES_SSL_MODE', 'disable')  # disable, require, verify-ca, verify-full
        
        # Таймауты
        self.command_timeout: int = int(os.getenv('POSTGRES_COMMAND_TIMEOUT', 60))  # секунды
        self.statement_cache_size: int = int(os.getenv('POSTGRES_STATEMENT_CACHE_SIZE', 100))
        
        # Параметры для асинхронного логгера
        self.log_table: str = os.getenv('POSTGRES_LOG_TABLE', 'logs')
    
    @property
    def dsn(self) -> str:
        """
        Возвращает DSN (Data Source Name) для подключения к PostgreSQL
        """
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    def get_connection_params(self) -> dict:
        """
        Возвращает параметры подключения в формате, подходящем для asyncpg
        """
        return {
            'host': self.host,
            'port': self.port,
            'database': self.database,
            'user': self.user,
            'password': self.password,
            'min_size': self.min_pool_size,
            'max_size': self.max_pool_size,
            'command_timeout': self.command_timeout,
            'statement_cache_size': self.statement_cache_size,
        }


# Пример использования
if __name__ == "__main__":
    config = PostgresConfig()
    
    print("Параметры подключения к PostgreSQL:")
    print(f"DSN: {config.dsn}")
    print(f"Host: {config.host}")
    print(f"Port: {config.port}")
    print(f"Database: {config.database}")
    print(f"User: {config.user}")
    print(f"Min pool size: {config.min_pool_size}")
    print(f"Max pool size: {config.max_pool_size}")
    
    # Пример использования с PGConnector
    print("\nПример использования с PGConnector:")
    print("""
from connectors.pg_connector import PGConnector

pg_connector = PGConnector(
    host=config.host,
    port=config.port,
    database=config.database,
    user=config.user,
    password=config.password,
    min_pool_size=config.min_pool_size,
    max_pool_size=config.max_pool_size
)
""")