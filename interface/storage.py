"""
Storage Interface - Strategy pattern implementation for file storage connectors.

Allows switching between different storage providers (MinIO, S3, Azure Blob, etc.)
while maintaining the same API.
"""
from typing import Any, AsyncGenerator, Optional

from core.base_class.connectors import FileStorageConnector
from core.base_class.observer import EventPublisher
from interface.base import BaseInterface


class StorageInterface(BaseInterface):
    """
    High-level interface for file storage operations.
    
    Implements Strategy pattern - can switch between different storage providers
    (MinIO, S3, Azure Blob, etc.) transparently.
    """

    def __init__(
        self,
        worker: FileStorageConnector,
        name: Optional[str] = None,
        event_publisher: Optional[EventPublisher] = None,
    ):
        """
        Initialize Storage interface.

        Args:
            worker: Storage connector instance (e.g., MinIOConnector)
            name: Interface name (defaults to worker name)
            event_publisher: Optional event publisher for observability
        """
        super().__init__(worker, name, event_publisher)

    @property
    def worker(self) -> FileStorageConnector:
        """Get underlying storage connector"""
        return self._worker

    async def download_bytes(
        self,
        object_name: str,
        *,
        timeout: Optional[float] = 30.0,
        **kwargs: Any,
    ) -> bytes:
        """
        Download file as bytes.

        Args:
            object_name: Name of object to download
            timeout: Download timeout
            **kwargs: Additional arguments for download

        Returns:
            File content as bytes
        """
        return await self._execute_with_tracking(
            "download_bytes",
            self._worker.download,
            object_name,
            timeout=timeout,
            use_streaming=False,
            **kwargs,
            metadata={"object_name": object_name},
        )

    async def download_stream(
        self,
        object_name: str,
        *,
        timeout: Optional[float] = 30.0,
        **kwargs: Any,
    ) -> AsyncGenerator[bytes, None]:
        """
        Download file as stream.

        Args:
            object_name: Name of object to download
            timeout: Download timeout
            **kwargs: Additional arguments for download

        Yields:
            Chunks of file content as bytes
        """
        stream = await self._execute_with_tracking(
            "download_stream",
            self._worker.download,
            object_name,
            timeout=timeout,
            use_streaming=True,
            **kwargs,
            metadata={"object_name": object_name},
        )
        return stream
