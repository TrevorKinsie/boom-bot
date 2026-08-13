"""
In-Process Event Bus (Publisher / Subscriber).

Domain events produced by aggregates are published to an in-process event bus.
Read-model projections and cross-cutting observers subscribe to the bus and
react to events asynchronously within the same process.

The bus is intentionally synchronous and in-memory: the platform is a single
process deployed on a single machine, so an in-process bus provides the
observer wiring without the operational overhead of an external broker.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Type

from boombot.casino.application.event.domain_event import AbstractDomainEvent


class IGameObserver(ABC):
    """Marker interface for subscribers that react to domain events."""

    @abstractmethod
    def notify(self, event: AbstractDomainEvent) -> None:
        raise NotImplementedError


class IEventBus(ABC):
    """Port describing the publish / subscribe contract of the event bus."""

    @abstractmethod
    def publish(self, event: AbstractDomainEvent) -> None:
        raise NotImplementedError

    @abstractmethod
    def subscribe(
        self, observer: IGameObserver, event_type: Type[AbstractDomainEvent]
    ) -> None:
        raise NotImplementedError


class InProcessEventBus(IEventBus):
    """Synchronous in-process implementation of the event bus."""

    def __init__(self) -> None:
        self._subscriptions: dict[Type[AbstractDomainEvent], list[IGameObserver]] = {}
        self._catch_all: list[IGameObserver] = []

    def subscribe(
        self, observer: IGameObserver, event_type: Type[AbstractDomainEvent]
    ) -> None:
        self._subscriptions.setdefault(event_type, []).append(observer)

    def subscribe_all(self, observer: IGameObserver) -> None:
        """Subscribe an observer to every published event type."""
        self._catch_all.append(observer)

    def publish(self, event: AbstractDomainEvent) -> None:
        observers = list(self._subscriptions.get(type(event), []))
        observers.extend(self._catch_all)
        for observer in observers:
            observer.notify(event)
