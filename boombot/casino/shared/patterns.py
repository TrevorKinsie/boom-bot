"""
Re-usable Design Pattern Building Blocks.

Provides abstract templates for the creational and behavioural patterns used
throughout the casino platform so that each pattern is expressed consistently:

* :class:`AbstractFactory` - creates related families of domain objects.
* :class:`AbstractBuilder` - composes complex objects in a validated sequence.
* :class:`AbstractSpecification` - encapsulates a single business rule.
* :class:`AbstractCommand` / :class:`AbstractResult` - the command object model.

Concrete implementations live within their owning bounded context and extend
these templates.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

TCreation = TypeVar("TCreation")
TTarget = TypeVar("TTarget")


class AbstractFactory(ABC, Generic[TCreation]):
    """Template for factories that construct domain objects."""

    def __init__(self) -> None:
        self._created_count = 0

    @abstractmethod
    def create(self, *args: Any, **kwargs: Any) -> TCreation:
        """Create and return a new instance of the produced type."""
        raise NotImplementedError

    def create_many(self, count: int, *args: Any, **kwargs: Any) -> list[TCreation]:
        instances: list[TCreation] = []
        for _ in range(count):
            instances.append(self.create(*args, **kwargs))
        return instances


class AbstractBuilder(ABC, Generic[TTarget]):
    """Template for fluent builders that assemble a complex target object."""

    def __init__(self) -> None:
        self._target: TTarget | None = None

    @abstractmethod
    def build(self) -> TTarget:
        """Validate and return the fully assembled target."""
        raise NotImplementedError

    def reset(self) -> "AbstractBuilder[TTarget]":
        self._target = None
        return self


class AbstractSpecification(ABC):
    """Encapsulation of a single business rule as a predicate object."""

    @abstractmethod
    def is_satisfied_by(self, candidate: Any) -> bool:
        raise NotImplementedError

    def and_also(self, other: "AbstractSpecification") -> "AbstractSpecification":
        return _AndSpecification(self, other)

    def or_else(self, other: "AbstractSpecification") -> "AbstractSpecification":
        return _OrSpecification(self, other)

    def not_specification(self) -> "AbstractSpecification":
        return _NotSpecification(self)


class _AndSpecification(AbstractSpecification):
    def __init__(self, left: AbstractSpecification, right: AbstractSpecification) -> None:
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: Any) -> bool:
        return self._left.is_satisfied_by(candidate) and self._right.is_satisfied_by(
            candidate
        )


class _OrSpecification(AbstractSpecification):
    def __init__(self, left: AbstractSpecification, right: AbstractSpecification) -> None:
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: Any) -> bool:
        return self._left.is_satisfied_by(candidate) or self._right.is_satisfied_by(
            candidate
        )


class _NotSpecification(AbstractSpecification):
    def __init__(self, inner: AbstractSpecification) -> None:
        self._inner = inner

    def is_satisfied_by(self, candidate: Any) -> bool:
        return not self._inner.is_satisfied_by(candidate)


class AbstractCommand(ABC):
    """Marker base class for write-side command objects (CQRS)."""

    def __init__(self) -> None:
        self._command_id: str | None = None

    def get_command_id(self) -> str | None:
        return self._command_id

    def assign_command_id(self, command_id: str) -> None:
        self._command_id = command_id


class AbstractQuery(ABC):
    """Marker base class for read-side query objects (CQRS)."""