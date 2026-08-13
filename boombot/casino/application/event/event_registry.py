"""
Domain Event Type Registry.

Persistence requires a deterministic mapping between the discriminator string
stored with an event record and the concrete event class that reconstructs it.
The registry performs that resolution and is the single registration point for
new domain event types.
"""

from __future__ import annotations

from typing import Type

from boombot.casino.application.event.domain_event import (
    AbstractDomainEvent,
    WalletCreatedEvent,
    FundsDebitedEvent,
    FundsCreditedEvent,
    WalletResetEvent,
    FreeSpinAwardedEvent,
    FreeSpinRedeemedEvent,
    WageredRecordedEvent,
)
from boombot.casino.shared.exceptions import JsonDeserializationException


class EventTypeRegistry:
    """Maps event type discriminators to their concrete event classes."""

    def __init__(self) -> None:
        self._registry: dict[str, Type[AbstractDomainEvent]] = {}

    def register(self, event_type: Type[AbstractDomainEvent]) -> "EventTypeRegistry":
        self._registry[event_type.EVENT_TYPE] = event_type
        return self

    def resolve(self, discriminator: str) -> Type[AbstractDomainEvent]:
        try:
            return self._registry[discriminator]
        except KeyError as exc:
            raise JsonDeserializationException(
                f"No domain event class registered for discriminator: {discriminator}"
            ) from exc

    def get_all_event_types(self) -> list[Type[AbstractDomainEvent]]:
        return list(self._registry.values())


def create_default_event_type_registry() -> EventTypeRegistry:
    """Build the registry with every wallet lifecycle event registered."""
    registry = EventTypeRegistry()
    for event_type in (
        WalletCreatedEvent,
        FundsDebitedEvent,
        FundsCreditedEvent,
        WalletResetEvent,
        FreeSpinAwardedEvent,
        FreeSpinRedeemedEvent,
        WageredRecordedEvent,
    ):
        registry.register(event_type)
    return registry
