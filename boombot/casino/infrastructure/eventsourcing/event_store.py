"""
Event Store Port and Snapshot Policy.

The event store is the persistence port of the write side. It exposes
append-only semantics for committed domain events and snapshot read/write
operations. Concrete adapters (JSON, SQLite) implement this port and are
selected through the dependency injection container.

Snapshotting is governed by :class:`SnapshotPolicy`, which decides when a
compacted aggregate snapshot should be written to bound the replay cost of
long event streams.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from boombot.casino.application.event.domain_event import AbstractDomainEvent
from boombot.casino.shared.value_objects import AggregateVersion


class IEventStore(ABC):
    """Port describing append-only persistence of domain events."""

    @abstractmethod
    def append(self, aggregate_id: str, events: list[AbstractDomainEvent]) -> None:
        """Persist a batch of committed events for a single aggregate."""
        raise NotImplementedError

    @abstractmethod
    def load(self, aggregate_id: str) -> list[AbstractDomainEvent]:
        """Load the full committed event stream for an aggregate."""
        raise NotImplementedError

    @abstractmethod
    def load_all_events(self) -> list[AbstractDomainEvent]:
        """Load the complete event log across all aggregates."""
        raise NotImplementedError

    @abstractmethod
    def save_snapshot(
        self, aggregate_id: str, version: AggregateVersion, state: dict[str, Any]
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_snapshot(self, aggregate_id: str) -> Optional[tuple[AggregateVersion, dict[str, Any]]]:
        """Return (version, state) for a stored snapshot, or None."""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError


class SnapshotPolicy:
    """Decides when an aggregate's stream should be compacted into a snapshot."""

    def __init__(self, snapshot_threshold: int = 50) -> None:
        if snapshot_threshold < 1:
            raise ValueError("Snapshot threshold must be a positive integer.")
        self._snapshot_threshold = snapshot_threshold

    def get_threshold(self) -> int:
        return self._snapshot_threshold

    def should_take_snapshot(
        self, uncommitted_events: int, committed_version: int
    ) -> bool:
        return committed_version + uncommitted_events >= self._snapshot_threshold
