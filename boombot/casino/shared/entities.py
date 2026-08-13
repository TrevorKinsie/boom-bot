"""
Entity Base Hierarchy.

Entities are domain objects with a continuous identity rather than structural
equality. This module provides a graduated inheritance chain of abstract
entity base classes, from the most general identifiable object down to an
auditable, versioned aggregate root. Each subclass adds one cohesive concern:

* :class:`AbstractIdentifiable` - has a stable identity.
* :class:`AbstractEntity` - an identifiable object existing in time.
* :class:`AbstractAuditableEntity` - tracks authorship and a modified timestamp.
* :class:`AbstractVersionedEntity` - carries an optimistic-lock version token.

Bounded-context domain models extend the appropriate member of this chain.
"""

from __future__ import annotations

from abc import ABC
from datetime import datetime, timezone
from typing import Any, Optional

from boombot.casino.shared.value_objects import AggregateVersion


class AbstractIdentifiable(ABC):
    """Root of the entity hierarchy; every entity has a stable identifier."""

    __slots__ = ("_identity",)

    def __init__(self, identity: str) -> None:
        if not identity:
            raise ValueError("An entity identifier must not be empty.")
        self._identity = identity

    def get_identity(self) -> str:
        return self._identity


class AbstractEntity(AbstractIdentifiable):
    """An identifiable object that exists in time."""

    __slots__ = ("_identity", "_created_at")

    def __init__(self, identity: str, created_at: Optional[datetime] = None) -> None:
        super().__init__(identity)
        self._created_at = created_at or datetime.now(timezone.utc)

    def get_created_at(self) -> datetime:
        return self._created_at


class AbstractAuditableEntity(AbstractEntity):
    """An entity that tracks its author and the last modification time."""

    __slots__ = ("_identity", "_created_at", "_created_by", "_updated_at")

    def __init__(
        self,
        identity: str,
        created_by: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        super().__init__(identity, created_at)
        self._created_by = created_by
        self._updated_at = self._created_at

    def get_created_by(self) -> Optional[str]:
        return self._created_by

    def get_updated_at(self) -> datetime:
        return self._updated_at

    def mark_modified(self) -> None:
        self._updated_at = datetime.now(timezone.utc)


class AbstractVersionedEntity(AbstractAuditableEntity):
    """An auditable entity carrying an optimistic-lock version token."""

    __slots__ = ("_identity", "_created_at", "_created_by", "_updated_at", "_version")

    def __init__(
        self,
        identity: str,
        version: AggregateVersion,
        created_by: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        super().__init__(identity, created_by, created_at)
        self._version = version

    def get_version(self) -> AggregateVersion:
        return self._version

    def increment_version(self) -> AggregateVersion:
        self._version = self._version.next()
        return self._version

    def assert_version_matches(self, expected: AggregateVersion) -> None:
        """Optimistic-lock guard; raises on version mismatch at the call site."""
        if self._version != expected:
            from boombot.casino.shared.exceptions import ConcurrentModificationException

            raise ConcurrentModificationException(
                f"Version conflict: expected {expected.number()} "
                f"but aggregate was at {self._version.number()}."
            )


class AbstractAggregateRoot(AbstractVersionedEntity):
    """A versioned entity that owns and enforces invariants over a boundary.

    Aggregate roots are the entry point for all mutations to their internal
    state graph. In the event-sourced model, aggregation is performed by
    replaying the aggregate's domain event stream.
    """

    __slots__ = ("_identity", "_created_at", "_created_by", "_updated_at", "_version")

    def __init__(
        self,
        identity: str,
        version: AggregateVersion | None = None,
        created_by: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        super().__init__(
            identity, version or AggregateVersion(0), created_by, created_at
        )

    # --- Serialization contract (implemented by concrete aggregates) ---
    def to_state_dictionary(self) -> dict[str, Any]:
        """Return a plain-dictionary serialization of the aggregate state."""
        raise NotImplementedError

    @classmethod
    def from_state_dictionary(cls, identity: str, state: dict[str, Any]) -> "AbstractAggregateRoot":
        """Reconstitute an aggregate from a plain dictionary."""
        raise NotImplementedError