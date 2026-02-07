"""
Database Interface - Strategy pattern implementation for DB connectors.

Allows switching between different database providers (PostgreSQL, MySQL, etc.)
while maintaining the same API.
"""

from typing import Any, Dict, List, Optional

from utils.observer import EventPublisher
from core.base_class.protocols import IDBConnector
from core.base_class.base_interface import BaseInterface
from core.registry import register_interface


@register_interface("Postgres")
class DBInterface(BaseInterface):
    """
    High-level interface for database operations.

    Implements Strategy pattern - can switch between different DB providers
    (PostgreSQL, MySQL, etc.) transparently.
    """

    def __init__(
        self,
        worker: IDBConnector,
        name: Optional[str] = None,
        event_publisher: Optional[EventPublisher] = None,
    ) -> None:
        """
        Initialize DB interface.

        Args:
            worker: DB connector instance (e.g., PGConnector)
            name: Interface name (defaults to worker name)
            event_publisher: Optional event publisher for observability
        """
        super().__init__(worker, name, event_publisher)

    @property
    def worker(self) -> IDBConnector:
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
            metadata={"query": query[:100]},
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

    async def execute_many(self, query: str, args_list: List[tuple]) -> str:
        """
        Execute query multiple times with different parameters.

        Args:
            query: SQL query to execute
            args_list: List of parameter tuples

        Returns:
            Command result
        """
        return await self._execute_with_tracking(
            "execute_many",
            self._worker.execute_many,
            query,
            args_list,
            metadata={"query": query[:100], "count": len(args_list)},
        )

    async def bulk_insert(
        self,
        table: str,
        columns: List[str],
        rows: List[tuple],
        batch_size: int = 1000
    ) -> int:
        """
        Perform bulk insert with batching.

        Args:
            table: Target table name
            columns: Column names
            rows: List of row tuples to insert
            batch_size: Number of rows per batch

        Returns:
            Total number of inserted rows
        """
        return await self._execute_with_tracking(
            "bulk_insert",
            self._worker.bulk_insert,
            table,
            columns,
            rows,
            batch_size,
            metadata={
                "table": table,
                "columns_count": len(columns),
                "rows_count": len(rows),
                "batch_size": batch_size
            },
        )

    async def health_check(self) -> bool:
        """
        Check database connectivity.

        Returns:
            True if database is accessible, False otherwise
        """
        return await self._execute_with_tracking(
            "health_check",
            self._worker.health_check,
            metadata={"check_type": "db_connectivity"},
        )

    async def get_pool_stats(self) -> Dict[str, Any]:
        """
        Get connection pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        return await self._execute_with_tracking(
            "get_pool_stats",
            self._worker.get_pool_stats,
            metadata={"info_type": "pool_stats"},
        )
