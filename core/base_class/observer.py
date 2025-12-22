"""
Observer pattern implementation for connector events.

Provides event-driven architecture for logging, metrics, and monitoring.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable


class EventType(str, Enum):
    """Types of connector events"""
    OPERATION_STARTED = "operation_started"
    OPERATION_COMPLETED = "operation_completed"
    OPERATION_FAILED = "operation_failed"
    CONNECTOR_INITIALIZED = "connector_initialized"
    CONNECTOR_SHUTDOWN = "connector_shutdown"
    HEALTH_CHECK = "health_check"


@dataclass
class ConnectorEvent:
    """Event emitted by connectors/interfaces"""

    event_type: EventType
    connector_name: str
    interface_name: Optional[str] = None
    operation_name: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration_ms: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization"""
        return {
            "event_type": self.event_type.value,
            "connector_name": self.connector_name,
            "interface_name": self.interface_name,
            "operation_name": self.operation_name,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata,
        }


class EventObserver(ABC):
    """Base class for event observers"""

    @abstractmethod
    async def on_event(self, event: ConnectorEvent) -> None:
        """Handle connector event"""
        pass


class EventPublisher:
    """
    Event publisher for connector events.
    Supports multiple observers (logger, metrics, tracing, etc.)
    """

    def __init__(self):
        self._observers: List[EventObserver] = []

    def subscribe(self, observer: EventObserver) -> None:
        """Subscribe observer to events"""
        if observer not in self._observers:
            self._observers.append(observer)

    def unsubscribe(self, observer: EventObserver) -> None:
        """Unsubscribe observer from events"""
        if observer in self._observers:
            self._observers.remove(observer)

    async def publish(self, event: ConnectorEvent) -> None:
        """Publish event to all observers"""
        for observer in self._observers:
            try:
                await observer.on_event(event)
            except Exception:
                # Don't fail if observer fails - log and continue
                pass


class LoggingObserver(EventObserver):
    """Observer that logs all events with configurable detail levels"""

    def __init__(self, logger):
        self.logger = logger

    async def on_event(self, event: ConnectorEvent) -> None:
        """Log event with appropriate level"""
        # Determine log level
        if not event.success:
            level = logging.ERROR
        elif event.event_type == EventType.OPERATION_STARTED:
            # Only log started events in DEBUG mode
            level = logging.DEBUG
        else:
            level = logging.INFO

        # Build message
        message = (
            f"[{event.event_type.value}] "
            f"{event.interface_name or event.connector_name}::"
            f"{event.operation_name or 'unknown'}"
        )

        if not event.success:
            message += " - FAILED"
        elif event.event_type == EventType.OPERATION_COMPLETED:
            message += " - OK"

        if event.duration_ms is not None:
            message += f" ({event.duration_ms:.2f}ms)"

        if event.error:
            message += f" - {event.error}"

        # Add metadata in DEBUG mode
        extra = {"event": event.to_dict()}
        if event.metadata and self.logger.level == logging.DEBUG:
            extra["metadata"] = event.metadata

        # Log with appropriate level
        self.logger.log(level, message, extra=extra)


class MetricsObserver(EventObserver):
    """Observer for collecting metrics (can be extended with Prometheus, etc.)"""

    def __init__(self):
        self._metrics: Dict[str, List[float]] = {}

    async def on_event(self, event: ConnectorEvent) -> None:
        """Collect metrics from event"""
        if event.duration_ms is not None:
            key = f"{event.connector_name}.{event.operation_name or 'unknown'}"
            if key not in self._metrics:
                self._metrics[key] = []
            self._metrics[key].append(event.duration_ms)

    def get_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get collected metrics"""
        result = {}
        for key, durations in self._metrics.items():
            if durations:
                result[key] = {
                    "count": len(durations),
                    "avg_ms": sum(durations) / len(durations),
                    "min_ms": min(durations),
                    "max_ms": max(durations),
                }
        return result

    def reset(self) -> None:
        """Reset collected metrics"""
        self._metrics.clear()


class TracingObserver(EventObserver):
    """Observer for distributed tracing (can be extended with OpenTelemetry)"""

    def __init__(self):
        self._traces: List[ConnectorEvent] = []

    async def on_event(self, event: ConnectorEvent) -> None:
        """Store trace event"""
        self._traces.append(event)

    def get_traces(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent traces"""
        return [e.to_dict() for e in self._traces[-limit:]]

    def clear(self) -> None:
        """Clear traces"""
        self._traces.clear()

