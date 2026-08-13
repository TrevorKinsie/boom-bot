"""
Event-Sourced Aggregate Base.

An event-sourced aggregate mutates itself exclusively by applying domain
events. Applied events are appended to the aggregate's list of uncommitted
events; once the aggregate is persisted, those events are considered
committed. Reconstruction (replay) is performed by folding a stream of stored
events through :meth:`apply` in order.
"""

from __future__ import annotations

from typing import Any, Optional

from boombot.casino.application.event.domain_event import AbstractDomainEvent
from boombot.casino.shared.entities import AbstractAggregateRoot
from boombot.casino.shared.value_objects import AggregateVersion


class AbstractEventSourcedAggregate(AbstractAggregateRoot):
    """Base class for aggregates whose state is derived from an event stream."""

    def __init__(
        self,
        identity: str,
        version: AggregateVersion | None = None,
        created_by: Optional[str] = None,
    ) -> None:
        super().__init__(identity, version or AggregateVersion(0), created_by)
        self._uncommitted_events: list[AbstractDomainEvent] = []

    # --- Event application ---
    def raise_event(self, event: AbstractDomainEvent) -> None:
        """Apply a domain event to aggregate state and stage it for commit."""
        event.assign_version(self._version.next())
        self.apply(event)
        self._version = event.get_version()
        self._uncommitted_events.append(event)

    def apply(self, event: AbstractDomainEvent) -> None:
        """Fold a single event into the aggregate's state.

        Concrete aggregates implement this method with an explicit dispatch
        over the event types they handle.
        """
        raise NotImplementedError

    # --- Commit protocol ---
    def get_uncommitted_events(self) -> list[AbstractDomainEvent]:
        return list(self._uncommitted_events)

    def commit(self) -> None:
        """Clear the staged uncommitted events after a successful persist."""
        self._uncommitted_events.clear()

    def has_uncommitted_events(self) -> bool:
        return len(self._uncommitted_events) > 0

    # --- Replay ---
    def replay(self, events: list[AbstractDomainEvent]) -> "AbstractEventSourcedAggregate":
        """Reconstruct aggregate state from a stream of committed events."""
        self._version = AggregateVersion(0)
        for event in sorted(events, key=lambda evt: evt.get_version().number()):
            event.assign_version(event.get_version())
            self.apply(event)
            self._version = event.get_version()
        self._uncommitted_events.clear()
        return self

    # --- Snapshot projection ---
    def to_snapshot_state(self) -> dict[str, Any]:
        """Return a plain-dictionary snapshot of current aggregate state."""
        state = self.to_state_dictionary()
        state["version"] = self._version.number()
        return state

    @classmethod
    def from_snapshot_state(
        cls, identity: str, snapshot: dict[str, Any]
    ) -> "AbstractEventSourcedAggregate":
        aggregate = cls.from_state_dictionary(identity, snapshot)
        aggregate._version = AggregateVersion(int(snapshot.get("version", 0)))
        return aggregate
