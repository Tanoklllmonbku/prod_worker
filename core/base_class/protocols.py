"""
Protocol-based type definitions for connectors.
These provide structural typing (duck typing) without inheritance overhead.
Useful for type checking and IDE support while keeping flexibility.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


class ILLMConnector(Protocol):
    """Protocol for LLM connectors - structural typing"""

    @property
    def name(self) -> str:
        """Connector name identifier"""
        ...

    async def initialize(self) -> None:
        """Initialize connector resources"""
        ...

    async def shutdown(self) -> None:
        """Cleanup connector resources"""
        ...

    async def health_check(self) -> bool:
        """Check connector health"""
        ...

    def is_healthy(self) -> bool:
        """Get cached health status"""
        ...

    async def chat(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        file_ids: Optional[List[str]] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        timeout: Optional[float] = None,
    ) -> Any:
        """Chat with LLM"""
        ...

    async def upload_file(
        self,
        file_data: Any,
        filename: Optional[str] = None,
        mime_type: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Optional[str]:
        """Upload file and return file_id"""
        ...

    async def upload_files_concurrent(
        self,
        files: List[Dict[str, Any]],
        timeout: Optional[float] = None,
    ) -> List[str]:
        """Upload multiple files concurrently"""
        ...

    async def delete_file(
        self,
        file_id: str,
        timeout: Optional[float] = None,
    ) -> bool:
        """Delete file from LLM service"""
        ...


class IQueueConnector(Protocol):
    """Protocol for queue/broker connectors"""

    @property
    def name(self) -> str:
        """Connector name identifier"""
        ...

    async def initialize(self) -> None:
        """Initialize connector resources"""
        ...

    async def shutdown(self) -> None:
        """Cleanup connector resources"""
        ...

    async def health_check(self) -> bool:
        """Check connector health"""
        ...

    def is_healthy(self) -> bool:
        """Get cached health status"""
        ...

    async def publish(
        self,
        topic: str,
        datagram_id: str,
        data: Dict[str, Any],
        *,
        key: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Publish single message"""
        ...

    async def batch_publish(
        self,
        topic: str,
        messages: List[Any],
        **kwargs: Any,
    ) -> None:
        """Publish batch of messages"""
        ...

    async def subscribe(
        self,
        topics: List[str],
        group_id: str,
        **kwargs: Any,
    ) -> None:
        """Subscribe to topics"""
        ...

    async def consume(self) -> Any:
        """Consume next message"""
        ...


class IFileStorageConnector(Protocol):
    """Protocol for file/blob storage connectors"""

    @property
    def name(self) -> str:
        """Connector name identifier"""
        ...

    async def initialize(self) -> None:
        """Initialize connector resources"""
        ...

    async def shutdown(self) -> None:
        """Cleanup connector resources"""
        ...

    async def health_check(self) -> bool:
        """Check connector health"""
        ...

    def is_healthy(self) -> bool:
        """Get cached health status"""
        ...

    async def download(
        self,
        object_name: str,
        *,
        timeout: Optional[float] = None,
        use_streaming: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Download file (bytes or AsyncGenerator)"""
        ...


class IDBConnector(Protocol):
    """Protocol for database connectors"""

    @property
    def name(self) -> str:
        """Connector name identifier"""
        ...

    async def initialize(self) -> None:
        """Initialize connector resources"""
        ...

    async def shutdown(self) -> None:
        """Cleanup connector resources"""
        ...

    async def health_check(self) -> bool:
        """Check connector health"""
        ...

    def is_healthy(self) -> bool:
        """Get cached health status"""
        ...

    async def load(self, query: str, *args: Any) -> List[Dict[str, Any]]:
        """Execute SELECT and return list of rows"""
        ...

    async def load_one(self, query: str, *args: Any) -> Optional[Dict[str, Any]]:
        """Execute SELECT and return single row"""
        ...

    async def execute(self, query: str, *args: Any) -> Any:
        """Execute DML (INSERT/UPDATE/DELETE)"""
        ...
