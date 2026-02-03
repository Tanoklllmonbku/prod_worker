import asyncio
import logging
import inspect
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict, Any
import asyncpg
import queue
import threading
import time
from datetime import datetime


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


class AsyncPGHandler(logging.Handler):
    def __init__(self, dsn: str, table: str = 'logs', max_queue_size: int = 1000):
        super().__init__()
        self.dsn = dsn
        self.table = table
        self.max_queue_size = max_queue_size
        self.log_queue = queue.Queue(maxsize=max_queue_size)
        self.running = True
        
        # Start the background thread for processing logs
        self.worker_thread = threading.Thread(target=self._process_logs, daemon=True)
        self.worker_thread.start()
        
        # Initialize connection pool later
        self.pool = None
        asyncio.run(self._initialize_pool())

    async def _initialize_pool(self):
        """Initialize the connection pool asynchronously."""
        self.pool = await asyncpg.create_pool(
            self.dsn,
            min_size=1,
            max_size=5,
            command_timeout=60
        )
        # Create table if not exists
        await self._create_table_if_not_exists()

    async def _create_table_if_not_exists(self):
        """Create logs table if it doesn't exist."""
        if not self.pool:
            return
            
        async with self.pool.acquire() as conn:
            await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table} (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                level VARCHAR(10) NOT NULL,
                logger_name VARCHAR(255) NOT NULL,
                cls VARCHAR(255),
                func VARCHAR(255),
                message TEXT NOT NULL
            );
            """)

    def emit(self, record):
        """Add log record to queue for async processing."""
        try:
            # Format the record here before putting in queue
            formatted_msg = self.format(record)
            
            log_entry = {
                'created_at': datetime.utcnow(),
                'level': record.levelname,
                'logger_name': record.name,
                'cls': getattr(record, 'cls', None),
                'func': getattr(record, 'func', None),
                'message': formatted_msg
            }
            
            # Put log entry in queue (non-blocking)
            try:
                self.log_queue.put_nowait(log_entry)
            except queue.Full:
                # Log queue is full, drop the oldest log
                try:
                    self.log_queue.get_nowait()  # Remove oldest
                    self.log_queue.put_nowait(log_entry)  # Add new
                except queue.Empty:
                    pass  # Queue became empty between checks, ignore
        except Exception:
            self.handleError(record)

    def _process_logs(self):
        """Background thread function to process logs from queue."""
        while self.running:
            try:
                # Get log entries from queue with timeout
                batch = []
                batch_start_time = time.time()
                
                # Collect logs for batching
                while len(batch) < 100 and (time.time() - batch_start_time) < 1.0:
                    try:
                        log_entry = self.log_queue.get(timeout=0.1)
                        batch.append(log_entry)
                    except queue.Empty:
                        break
                
                if batch:
                    # Process the batch
                    asyncio.run(self._insert_batch_async(batch))
                    
            except Exception as e:
                # Error in processing, but we don't want to crash the worker thread
                print(f"Error in AsyncPGHandler worker: {e}")

    async def _insert_batch_async(self, batch: list):
        """Insert a batch of log records into the database."""
        if not self.pool:
            return
            
        try:
            async with self.pool.acquire() as conn:
                # Prepare the insert query
                query = f"""
                INSERT INTO {self.table}
                (created_at, level, logger_name, cls, func, message)
                VALUES ($1, $2, $3, $4, $5, $6)
                """
                
                # Prepare data for batch insert
                values = [
                    (
                        entry['created_at'],
                        entry['level'],
                        entry['logger_name'],
                        entry['cls'],
                        entry['func'],
                        entry['message']
                    )
                    for entry in batch
                ]
                
                # Execute batch insert
                await conn.executemany(query, values)
                
        except Exception as e:
            print(f"Error inserting logs to database: {e}")
            # Re-queue failed logs if possible
            for entry in batch:
                try:
                    self.log_queue.put_nowait(entry)
                except queue.Full:
                    # Queue is full, drop the log
                    pass

    def close(self):
        """Close the handler and stop the worker thread."""
        self.running = False
        if self.pool:
            self.pool.close()
            asyncio.run(self.pool.wait_closed())
        super().close()


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
        # Create async PG handler
        pg_handler = AsyncPGHandler(pg_dsn)
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
        pg_dsn=getattr(config, 'log_pg_dsn', None),  # Can be added to config if needed
        enable_debug=config.log_enable_debug,
    )
