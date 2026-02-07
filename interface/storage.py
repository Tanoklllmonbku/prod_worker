"""
Storage Interface - Strategy pattern implementation for file storage connectors.

Allows switching between different storage providers (MinIO, S3, Azure Blob, etc.)
while maintaining the same API.
"""

from typing import Any, AsyncGenerator, Optional

from utils.observer import EventPublisher
from core.base_class.protocols import IFileStorageConnector
from core.base_class.base_interface import BaseInterface
from core.registry import register_interface


@register_interface("Minio")
class StorageInterface(BaseInterface):
    """
    High-level interface for file storage operations.

    Implements Strategy pattern - can switch between different storage providers
    (MinIO, S3, Azure Blob, etc.) transparently.
    """

    def __init__(
        self,
        worker: IFileStorageConnector,
        name: Optional[str] = None,
        event_publisher: Optional[EventPublisher] = None,
    ) -> None:
        """
        Initialize Storage interface.

        Args:
            worker: Storage connector instance (e.g., MinIOConnector)
            name: Interface name (defaults to worker name)
            event_publisher: Optional event publisher for observability
        """
        super().__init__(worker, name, event_publisher)

    async def get_file(self, file_path: str) -> bytes:
        """Alias for download_bytes - used by documents_service"""
        return await self.download_bytes(object_name=file_path)

    @property
    def worker(self) -> IFileStorageConnector:
        """Get underlying storage connector"""
        return self._worker

    async def upload_file(
            self,
            file_data: bytes,
            filename: str,
            *,
            timeout: Optional[float] = 30.0,
            **kwargs: Any,
    ) -> str:
        """Upload file to MinIO and return object name"""
        object_name = f"documents/{filename}"
        await self._execute_with_tracking(
            "upload_file",
            self._worker.upload,
            object_name,
            file_data,
            timeout=timeout,
            **kwargs,
            metadata={"object_name": object_name, "filename": filename},
        )
        return object_name

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
