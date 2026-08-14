"""
SQLite Event Store Adapter.

Implements :class:`IEventStore` over an embedded SQLite database. Domain events
are stored in a dedicated ``casino_events`` table and compacted snapshots in a
companion ``casino_snapshots`` table. SQLite is already a dependency of the
chess feature, so this adapter adds no new runtime dependencies while
demonstrating pluggable ports-and-adapters persistence.

Writes are serialised through a single connection guarded by a re-entrant
lock; transactions are committed per append batch.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

from boombot.casino.application.event.domain_event import AbstractDomainEvent
from boombot.casino.application.event.event_registry import EventTypeRegistry
from boombot.casino.infrastructure.eventsourcing.event_store import IEventStore
from boombot.casino.shared.exceptions import (
    ConcurrentModificationException,
    JsonSerializationException,
    PersistenceException,
)
from boombot.casino.shared.value_objects import AggregateVersion

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS casino_events (
    event_id TEXT PRIMARY KEY,
    aggregate_id TEXT NOT NULL,
    occurred_on TEXT NOT NULL,
    version INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(aggregate_id, version)
);
CREATE TABLE IF NOT EXISTS casino_snapshots (
    aggregate_id TEXT PRIMARY KEY,
    version INTEGER NOT NULL,
    state_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_casino_events_aggregate
    ON casino_events (aggregate_id, version);
"""


class SqliteEventStoreAdapter(IEventStore):
    """SQLite-backed append-only event store."""

    def __init__(self, database_path: Path, event_registry: EventTypeRegistry) -> None:
        self._database_path = Path(database_path)
        self._event_registry = event_registry
        self._lock = threading.RLock()
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self._database_path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        with self._lock:
            self._connection.executescript(_SCHEMA)
            self._connection.commit()

    def append(self, aggregate_id: str, events: list[AbstractDomainEvent]) -> None:
        if not events:
            return
        try:
            with self._lock:
                cursor = self._connection.cursor()
                # Optimistic concurrency: verify the incoming events start right
                # after the last persisted event for this aggregate. If the
                # expected starting version does not match what is persisted,
                # a conflicting concurrent write has occurred.
                first_version = events[0].get_version().number()
                cursor.execute(
                    "SELECT MAX(version) FROM casino_events WHERE aggregate_id = ?",
                    (aggregate_id,),
                )
                row = cursor.fetchone()
                committed_version = row[0] if row and row[0] is not None else 0
                if first_version <= committed_version:
                    raise ConcurrentModificationException(
                        f"Concurrent modification detected for aggregate "
                        f"{aggregate_id}: expected version > {committed_version} "
                        f"but got {first_version}."
                    )
                for event in events:
                    record = event.to_dictionary()
                    cursor.execute(
                        "INSERT INTO casino_events "
                        "(event_id, aggregate_id, occurred_on, version, event_type, payload_json) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            event.get_event_id(),
                            aggregate_id,
                            event.get_occurred_on().isoformat(),
                            event.get_version().number(),
                            event.event_type(),
                            json.dumps(record, ensure_ascii=False),
                        ),
                    )
                self._connection.commit()
        except sqlite3.Error as exc:
            logger.error("Failed to append events to SQLite event store: %s", exc)
            raise PersistenceException(
                f"Could not append events for aggregate {aggregate_id}: {exc}"
            ) from exc

    def load(self, aggregate_id: str) -> list[AbstractDomainEvent]:
        try:
            with self._lock:
                cursor = self._connection.cursor()
                cursor.execute(
                    "SELECT payload_json FROM casino_events "
                    "WHERE aggregate_id = ? ORDER BY version ASC",
                    (aggregate_id,),
                )
                rows = cursor.fetchall()
            return [self._deserialize(json.loads(row["payload_json"])) for row in rows]
        except (sqlite3.Error, json.JSONDecodeError) as exc:
            logger.error("Failed to load events from SQLite event store: %s", exc)
            raise PersistenceException(
                f"Could not load events for aggregate {aggregate_id}: {exc}"
            ) from exc

    def load_all_events(self) -> list[AbstractDomainEvent]:
        try:
            with self._lock:
                cursor = self._connection.cursor()
                cursor.execute(
                    "SELECT payload_json FROM casino_events ORDER BY aggregate_id, version ASC"
                )
                rows = cursor.fetchall()
            return [self._deserialize(json.loads(row["payload_json"])) for row in rows]
        except (sqlite3.Error, json.JSONDecodeError) as exc:
            logger.error("Failed to load all events from SQLite event store: %s", exc)
            raise PersistenceException(f"Could not load all events: {exc}") from exc

    def save_snapshot(
        self, aggregate_id: str, version: AggregateVersion, state: dict[str, Any]
    ) -> None:
        try:
            with self._lock:
                self._connection.execute(
                    "INSERT OR REPLACE INTO casino_snapshots "
                    "(aggregate_id, version, state_json) VALUES (?, ?, ?)",
                    (aggregate_id, version.number(), json.dumps(state, ensure_ascii=False)),
                )
                self._connection.commit()
        except sqlite3.Error as exc:
            logger.error("Failed to save snapshot to SQLite event store: %s", exc)
            raise PersistenceException(
                f"Could not save snapshot for aggregate {aggregate_id}: {exc}"
            ) from exc

    def load_snapshot(
        self, aggregate_id: str
    ) -> Optional[tuple[AggregateVersion, dict[str, Any]]]:
        try:
            with self._lock:
                cursor = self._connection.cursor()
                cursor.execute(
                    "SELECT version, state_json FROM casino_snapshots WHERE aggregate_id = ?",
                    (aggregate_id,),
                )
                row = cursor.fetchone()
            if row is None:
                return None
            return AggregateVersion(int(row["version"])), json.loads(row["state_json"])
        except (sqlite3.Error, json.JSONDecodeError) as exc:
            logger.error("Failed to load snapshot from SQLite event store: %s", exc)
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
        with self._lock:
            self._connection.close()