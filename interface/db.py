"""
Database Interface - Strategy pattern implementation for DB connectors.

Allows switching between different database providers (PostgreSQL, MySQL, etc.)
while maintaining the same API.
"""
from typing import Any, Dict, List, Optional

from core.base_class.connectors import DBConnector
from core.base_class.observer import EventPublisher
from interface.base import BaseInterface


class DBInterface(BaseInterface):
    """
    High-level interface for database operations.
    
    Implements Strategy pattern - can switch between different DB providers
    (PostgreSQL, MySQL, etc.) transparently.
    """

    def __init__(
        self,
        worker: DBConnector,
        name: Optional[str] = None,
        event_publisher: Optional[EventPublisher] = None,
    ):
        """
        Initialize DB interface.

        Args:
            worker: DB connector instance (e.g., PGConnector)
            name: Interface name (defaults to worker name)
            event_publisher: Optional event publisher for observability
        """
        super().__init__(worker, name, event_publisher)

    @property
    def worker(self) -> DBConnector:
        """Get underlying DB connector"""
        return self._worker

    async def select(self, query: str, *args: Any) -> List[Dict[str, Any]]:
        """
        Execute SELECT query and return list of rows.

        Args:
            query: SQL SELECT query
            *args: Query parameters

        Returns:
            List of result rows as dictionaries
        """
        return await self._execute_with_tracking(
            "select",
            self._worker.load,
            query,
            *args,
            metadata={"query": query[:100]},  # Log first 100 chars
        )

    async def select_one(self, query: str, *args: Any) -> Optional[Dict[str, Any]]:
        """
        Execute SELECT query and return single row.

        Args:
            query: SQL SELECT query
            *args: Query parameters

        Returns:
            Single result row as dictionary or None
        """
        return await self._execute_with_tracking(
            "select_one",
            self._worker.load_one,
            query,
            *args,
            metadata={"query": query[:100]},
        )

    async def execute(self, query: str, *args: Any) -> Any:
        """
        Execute DML query (INSERT/UPDATE/DELETE).

        Args:
            query: SQL DML query
            *args: Query parameters

        Returns:
            Command result
        """
        return await self._execute_with_tracking(
            "execute",
            self._worker.execute,
            query,
            *args,
            metadata={"query": query[:100]},
        )
