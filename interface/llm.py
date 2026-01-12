"""
LLM Interface - Strategy pattern implementation for LLM connectors.

Allows switching between different LLM providers (GigaChat, OpenAI, etc.)
while maintaining the same API.
"""

from typing import Any, AsyncIterator, Dict, List, Optional

from core.base_class.base_interface import BaseInterface
from core.base_class.protocols import ILLMConnector
from utils.observer import EventPublisher


class LLMInterface(BaseInterface):
    """
    High-level interface for LLM operations.

    Implements Strategy pattern - can switch between different LLM providers
    (GigaChat, OpenAI, etc.) transparently.
    """

    def __init__(
        self,
        worker: ILLMConnector,
        name: Optional[str] = None,
        event_publisher: Optional[EventPublisher] = None,
    ) -> None:
        """
        Initialize LLM interface.

        Args:
            worker: LLM connector instance (e.g., GigaChatConnector)
            name: Interface name (defaults to worker name)
            event_publisher: Optional event publisher for observability
        """
        super().__init__(worker, name, event_publisher)

    @property
    def worker(self) -> ILLMConnector:
        """Get underlying LLM connector"""
        return self._worker

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
        """
        Chat with LLM.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            file_ids: Optional list of file IDs to attach
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            stream: If True, return streaming response
            timeout: Request timeout

        Returns:
            Response dict or AsyncIterator for streaming
        """
        return await self._execute_with_tracking(
            "chat",
            self._worker.chat,
            prompt,
            system_prompt=system_prompt,
            file_ids=file_ids,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            timeout=timeout,
        )

    async def stream_chat(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        file_ids: Optional[List[str]] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """
        Stream chat response.

        Convenience method that always returns streaming response.
        """
        result = await self.chat(
            prompt,
            system_prompt=system_prompt,
            file_ids=file_ids,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            timeout=timeout,
        )
        return result

    async def upload_file(
        self,
        file_data: Any,
        filename: Optional[str] = None,
        mime_type: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Optional[str]:
        """Upload file and return file ID"""
        return await self._execute_with_tracking(
            "upload_file",
            self._worker.upload_file,
            file_data,
            filename=filename,
            mime_type=mime_type,
            timeout=timeout,
        )

    async def upload_files(
        self,
        files: List[Dict[str, Any]],
        timeout: Optional[float] = None,
    ) -> List[str]:
        """Upload multiple files concurrently"""
        return await self._execute_with_tracking(
            "upload_files",
            self._worker.upload_files_concurrent,
            files,
            timeout=timeout,
        )

    async def delete_file(
        self,
        file_id: str,
        timeout: Optional[float] = None,
    ) -> bool:
        """Delete file from LLM service"""
        return await self._execute_with_tracking(
            "delete_file",
            self._worker.delete_file,
            file_id,
            timeout=timeout,
        )
