"""
JSON Event Store Adapter.

Implements :class:`IEventStore` over a JSON Lines (JSONL) append log. Each
committed domain event is serialized as a single JSON object on its own line
and appended to the log, preserving append-only semantics. Compacted snapshots
are maintained in a companion JSON file keyed by aggregate identifier.

The adapter is safe for concurrent writers within a single process because all
writes are funneled through a re-entrant lock.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Optional

from boombot.casino.application.event.domain_event import AbstractDomainEvent
from boombot.casino.application.event.event_registry import EventTypeRegistry
from boombot.casino.infrastructure.eventsourcing.event_store import IEventStore
from boombot.casino.shared.exceptions import (
    JsonSerializationException,
    PersistenceException,
)
from boombot.casino.shared.value_objects import AggregateVersion

logger = logging.getLogger(__name__)


class JsonEventStoreAdapter(IEventStore):
    """Append-only JSON Lines event store backed by the filesystem."""

    def __init__(self, event_log_path: Path, event_registry: EventTypeRegistry) -> None:
        self._event_log_path = Path(event_log_path)
        self._snapshot_path = self._event_log_path.with_suffix(".snapshots.json")
        self._event_registry = event_registry
        self._lock = threading.RLock()
        self._event_log_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, aggregate_id: str, events: list[AbstractDomainEvent]) -> None:
        if not events:
            return
        try:
            with self._lock, self._event_log_path.open("a", encoding="utf-8") as stream:
                for event in events:
                    stream.write(json.dumps(event.to_dictionary(), ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.error("Failed to append events to JSON event store: %s", exc)
            raise PersistenceException(
                f"Could not append events for aggregate {aggregate_id}: {exc}"
            ) from exc

    def load(self, aggregate_id: str) -> list[AbstractDomainEvent]:
        try:
            events: list[AbstractDomainEvent] = []
            if not self._event_log_path.exists():
                return events
            with self._lock, self._event_log_path.open("r", encoding="utf-8") as stream:
                for line in stream:
                    line = line.strip()
                    if not line:
                        continue
                    record = json.loads(line)
                    if record.get("aggregate_id") != aggregate_id:
                        continue
                    events.append(self._deserialize(record))
            return events
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to load events from JSON event store: %s", exc)
            raise PersistenceException(
                f"Could not load events for aggregate {aggregate_id}: {exc}"
            ) from exc

    def load_all_events(self) -> list[AbstractDomainEvent]:
        try:
            events: list[AbstractDomainEvent] = []
            if not self._event_log_path.exists():
                return events
            with self._lock, self._event_log_path.open("r", encoding="utf-8") as stream:
                for line in stream:
                    line = line.strip()
                    if not line:
                        continue
                    events.append(self._deserialize(json.loads(line)))
            return events
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to load all events from JSON event store: %s", exc)
            raise PersistenceException(f"Could not load all events: {exc}") from exc

    def save_snapshot(
        self, aggregate_id: str, version: AggregateVersion, state: dict[str, Any]
    ) -> None:
        try:
            snapshots: dict[str, dict[str, Any]] = {}
            if self._snapshot_path.exists():
                with self._lock, self._snapshot_path.open("r", encoding="utf-8") as stream:
                    snapshots = json.load(stream)
            snapshots[aggregate_id] = {"version": version.number(), "state": state}
            with self._lock, self._snapshot_path.open("w", encoding="utf-8") as stream:
                json.dump(snapshots, stream, ensure_ascii=False, indent=2)
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to save snapshot to JSON event store: %s", exc)
            raise PersistenceException(
                f"Could not save snapshot for aggregate {aggregate_id}: {exc}"
            ) from exc

    def load_snapshot(
        self, aggregate_id: str
    ) -> Optional[tuple[AggregateVersion, dict[str, Any]]]:
        try:
            if not self._snapshot_path.exists():
                return None
            with self._lock, self._snapshot_path.open("r", encoding="utf-8") as stream:
                snapshots = json.load(stream)
            record = snapshots.get(aggregate_id)
            if record is None:
                return None
            return AggregateVersion(int(record["version"])), record["state"]
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to load snapshot from JSON event store: %s", exc)
            raise PersistenceException(
                f"Could not load snapshot for aggregate {aggregate_id}: {exc}"
            ) from exc

    def _deserialize(self, record: dict[str, Any]) -> AbstractDomainEvent:
        event_type_name = record.get("event_type")
        if not event_type_name:
            raise JsonSerializationException(
                "Persisted event record is missing its event_type discriminator."
            )
        event_class = self._event_registry.resolve(event_type_name)
        return event_class.from_dictionary(record)

    def close(self) -> None:
        # JSON adapter holds no persistent handles; nothing to release.
        pass