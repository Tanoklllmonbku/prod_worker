from typing import Optional
from core.base_class.base_interface import BaseInterface
from core.base_class.protocols import IHTTPProtocol
from models.http_model import HealthResponse, StatusResponse
from utils.observer import EventPublisher
from core.registry import register_interface


@register_interface("FastApi")
class HTTPInterface(BaseInterface):

    def __init__(
        self,
        worker: IHTTPProtocol,
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
    def worker(self) -> IHTTPProtocol:
        """Get underlying LLM connector"""
        return self._worker
    
    async def health(self) -> HealthResponse:
        return self._execute_with_tracking(
            "health",
            self._worker.health
        )
        
    async def status(self) -> StatusResponse:
        return self._execute_with_tracking(
            "status",
            self._worker.status
        )
        