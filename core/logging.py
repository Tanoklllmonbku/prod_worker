import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional
import inspect
import psycopg2
from psycopg2.extras import execute_values

class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[2;36m',
        'INFO': '\033[0;32m',
        'WARNING': '\033[0;33m',
        'ERROR': '\033[0;31m',
        'CRITICAL': '\033[1;31m'
    }
    RESET = '\033[0m'

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)

class PGHandler(logging.Handler):
    def __init__(self, dsn, table='logs'):
        super().__init__()
        self.dsn = dsn
        self.table = table
        self.conn = psycopg2.connect(dsn)
        self.conn.autocommit = True
        self._create_table_if_not_exists()

    def _create_table_if_not_exists(self):
        with self.conn.cursor() as cur:
            cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table} (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL,
                level VARCHAR(10) NOT NULL,
                logger_name VARCHAR(255) NOT NULL,
                cls VARCHAR(255),
                func VARCHAR(255),
                message TEXT NOT NULL
            );
            """)

    def emit(self, record):
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {self.table} (created_at, level, logger_name, cls, func, message) VALUES (%s, %s, %s, %s, %s, %s)",
                    (self.formatTime(record),
                     record.levelname,
                     record.name,
                     getattr(record, 'cls', None),
                     getattr(record, 'func', None),
                     record.getMessage())
                )
        except Exception:
            self.handleError(record)

class ContextFilter(logging.Filter):
    def filter(self, record):
        frame = inspect.currentframe()
        frame = frame.f_back.f_back.f_back

        record.cls = None
        record.func = None

        if 'self' in frame.f_locals:
            record.cls = frame.f_locals['self'].__class__.__name__

        if frame.f_code:
            record.func = frame.f_code.co_name

        return True

def setup_logger(
        version: str,
        name: str = 'GUI',
        log_file: str = None,
        level: int = logging.INFO,
        pg_dsn: str = None
) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.hasHandlers():
        return logger

    file_formatter = logging.Formatter(
        f'{version} - %(cls)s - %(func)s - %(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = ColoredFormatter(
        f'{version} - %(cls)s - %(func)s - %(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.setLevel(level)

    logger.addFilter(ContextFilter())

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    if pg_dsn:
        pg_handler = PGHandler(pg_dsn)
        pg_handler.setFormatter(file_formatter)
        logger.addHandler(pg_handler)

    return logger

def get_logger(
    version: str = "1.0.0",
    name: str = "gigachatAPI",
    log_file: Optional[str] = None,
    level: Optional[int] = None,
    pg_dsn: Optional[str] = None,
    enable_debug: bool = False,
) -> logging.Logger:
    """
    Get configured logger instance.

    Args:
        version: Application version
        name: Logger name (default: "gigachatAPI")
        log_file: Optional log file path (default: "logs/system.log")
        level: Optional log level (default: INFO, or DEBUG if enable_debug=True)
        pg_dsn: Optional PostgreSQL DSN for database logging
        enable_debug: If True, sets level to DEBUG (overrides level parameter)

    Returns:
        Configured Logger instance
    """
    if log_file is None:
        log_file = "logs/system.log"

    if level is None:
        level = logging.DEBUG if enable_debug else logging.INFO

    return setup_logger(version, name, log_file, level=level, pg_dsn=pg_dsn)


def get_logger_from_config(config) -> logging.Logger:
    """
    Get logger configured from Config object.

    Args:
        config: Config instance with log_level, log_file, log_enable_debug

    Returns:
        Configured Logger instance
    """
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    level = level_map.get(config.log_level, logging.INFO)
    if config.log_enable_debug:
        level = logging.DEBUG

    return get_logger(
        version="1.0.0",
        name="gigachatAPI",
        log_file=config.log_file,
        level=level,
        pg_dsn=None,  # Can be added to config if needed
        enable_debug=config.log_enable_debug,
    )
