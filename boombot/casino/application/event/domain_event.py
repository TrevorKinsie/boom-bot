"""
Domain Event Model.

The casino platform persists state as an append-only stream of domain events.
Every domain event is immutable, carries a global identifier, the identifier
of the aggregate it mutated, and a timestamp of occurrence.

This module defines the base event hierarchy and the concrete wallet lifecycle
events, together with a serialization contract that allows the event store to
persist and later reconstruct events by their discriminator type name.
"""

from __future__ import annotations

from abc import ABC
from datetime import datetime, timezone
from typing import Any, ClassVar, Optional
from uuid import uuid4

from boombot.casino.shared.value_objects import Money, AggregateVersion


class AbstractDomainEvent(ABC):
    """Base class for every domain event emitted by the platform."""

    EVENT_TYPE: ClassVar[str] = "AbstractDomainEvent"

    def __init__(
        self,
        aggregate_id: str,
        occurred_on: Optional[datetime] = None,
        event_id: Optional[str] = None,
        version: Optional[AggregateVersion] = None,
    ) -> None:
        self._event_id = event_id or str(uuid4())
        self._aggregate_id = aggregate_id
        self._occurred_on = occurred_on or datetime.now(timezone.utc)
        self._version = version or AggregateVersion(0)

    def get_event_id(self) -> str:
        return self._event_id

    def get_aggregate_id(self) -> str:
        return self._aggregate_id

    def get_occurred_on(self) -> datetime:
        return self._occurred_on

    def get_version(self) -> AggregateVersion:
        return self._version

    def assign_version(self, version: AggregateVersion) -> None:
        self._version = version

    def event_type(self) -> str:
        return self.EVENT_TYPE

    # --- Serialization contract ---
    def to_dictionary(self) -> dict[str, Any]:
        base = {
            "event_id": self._event_id,
            "aggregate_id": self._aggregate_id,
            "occurred_on": self._occurred_on.isoformat(),
            "version": self._version.number(),
            "event_type": self.event_type(),
        }
        base.update(self._payload_dictionary())
        return base

    def _payload_dictionary(self) -> dict[str, Any]:
        return {}

    @classmethod
    def from_dictionary(cls, data: dict[str, Any]) -> "AbstractDomainEvent":
        event = cls._from_payload_dictionary(data.get("payload", {}))
        event._event_id = data.get("event_id")
        event._aggregate_id = data.get("aggregate_id")
        occurred = data.get("occurred_on")
        if occurred:
            event._occurred_on = datetime.fromisoformat(occurred)
        version = data.get("version")
        if version is not None:
            event._version = AggregateVersion(int(version))
        return event

    @classmethod
    def _from_payload_dictionary(cls, payload: dict[str, Any]) -> "AbstractDomainEvent":
        raise NotImplementedError


class AbstractWalletEvent(AbstractDomainEvent):
    """Base class for events that mutate a wallet aggregate."""


class WalletCreatedEvent(AbstractWalletEvent):
    """Emitted when a new wallet aggregate is provisioned."""

    EVENT_TYPE: ClassVar[str] = "WalletCreatedEvent"

    def __init__(
        self,
        aggregate_id: str,
        starting_balance: Money,
        occurred_on: Optional[datetime] = None,
        event_id: Optional[str] = None,
        version: Optional[AggregateVersion] = None,
    ) -> None:
        super().__init__(aggregate_id, occurred_on, event_id, version)
        self._starting_balance = starting_balance

    def get_starting_balance(self) -> Money:
        return self._starting_balance

    def _payload_dictionary(self) -> dict[str, Any]:
        return {
            "payload": {"starting_balance": self._starting_balance.to_decimal_string()}
        }

    @classmethod
    def _from_payload_dictionary(cls, payload: dict[str, Any]) -> "WalletCreatedEvent":
        return cls(
            aggregate_id="pending",
            starting_balance=Money(payload.get("starting_balance", "100.00")),
        )


class FundsDebitedEvent(AbstractWalletEvent):
    """Emitted when funds are reserved from a wallet (e.g. a wager)."""

    EVENT_TYPE: ClassVar[str] = "FundsDebitedEvent"

    def __init__(
        self,
        aggregate_id: str,
        amount: Money,
        reason: str,
        occurred_on: Optional[datetime] = None,
        event_id: Optional[str] = None,
        version: Optional[AggregateVersion] = None,
    ) -> None:
        super().__init__(aggregate_id, occurred_on, event_id, version)
        self._amount = amount
        self._reason = reason

    def get_amount(self) -> Money:
        return self._amount

    def get_reason(self) -> str:
        return self._reason

    def _payload_dictionary(self) -> dict[str, Any]:
        return {
            "payload": {
                "amount": self._amount.to_decimal_string(),
                "reason": self._reason,
            }
        }

    @classmethod
    def _from_payload_dictionary(cls, payload: dict[str, Any]) -> "FundsDebitedEvent":
        return cls(
            aggregate_id="pending",
            amount=Money(payload.get("amount", "0")),
            reason=payload.get("reason", ""),
        )


class FundsCreditedEvent(AbstractWalletEvent):
    """Emitted when funds are returned to a wallet (e.g. a payout)."""

    EVENT_TYPE: ClassVar[str] = "FundsCreditedEvent"

    def __init__(
        self,
        aggregate_id: str,
        amount: Money,
        reason: str,
        occurred_on: Optional[datetime] = None,
        event_id: Optional[str] = None,
        version: Optional[AggregateVersion] = None,
    ) -> None:
        super().__init__(aggregate_id, occurred_on, event_id, version)
        self._amount = amount
        self._reason = reason

    def get_amount(self) -> Money:
        return self._amount

    def get_reason(self) -> str:
        return self._reason

    def _payload_dictionary(self) -> dict[str, Any]:
        return {
            "payload": {
                "amount": self._amount.to_decimal_string(),
                "reason": self._reason,
            }
        }

    @classmethod
    def _from_payload_dictionary(cls, payload: dict[str, Any]) -> "FundsCreditedEvent":
        return cls(
            aggregate_id="pending",
            amount=Money(payload.get("amount", "0")),
            reason=payload.get("reason", ""),
        )


class WalletResetEvent(AbstractWalletEvent):
    """Emitted when a wallet balance is restored to the starting amount."""

    EVENT_TYPE: ClassVar[str] = "WalletResetEvent"

    def __init__(
        self,
        aggregate_id: str,
        reset_balance: Money,
        occurred_on: Optional[datetime] = None,
        event_id: Optional[str] = None,
        version: Optional[AggregateVersion] = None,
    ) -> None:
        super().__init__(aggregate_id, occurred_on, event_id, version)
        self._reset_balance = reset_balance

    def get_reset_balance(self) -> Money:
        return self._reset_balance

    def _payload_dictionary(self) -> dict[str, Any]:
        return {
            "payload": {"reset_balance": self._reset_balance.to_decimal_string()}
        }

    @classmethod
    def _from_payload_dictionary(cls, payload: dict[str, Any]) -> "WalletResetEvent":
        return cls(
            aggregate_id="pending",
            reset_balance=Money(payload.get("reset_balance", "100.00")),
        )


class FreeSpinAwardedEvent(AbstractWalletEvent):
    """Emitted when a free spin entitlement is granted."""

    EVENT_TYPE: ClassVar[str] = "FreeSpinAwardedEvent"

    def __init__(
        self,
        aggregate_id: str,
        count: int,
        occurred_on: Optional[datetime] = None,
        event_id: Optional[str] = None,
        version: Optional[AggregateVersion] = None,
    ) -> None:
        super().__init__(aggregate_id, occurred_on, event_id, version)
        self._count = count

    def get_count(self) -> int:
        return self._count

    def _payload_dictionary(self) -> dict[str, Any]:
        return {"payload": {"count": self._count}}

    @classmethod
    def _from_payload_dictionary(cls, payload: dict[str, Any]) -> "FreeSpinAwardedEvent":
        return cls(aggregate_id="pending", count=int(payload.get("count", 0)))


class FreeSpinRedeemedEvent(AbstractWalletEvent):
    """Emitted when a free spin entitlement is consumed."""

    EVENT_TYPE: ClassVar[str] = "FreeSpinRedeemedEvent"

    def __init__(
        self,
        aggregate_id: str,
        count: int,
        occurred_on: Optional[datetime] = None,
        event_id: Optional[str] = None,
        version: Optional[AggregateVersion] = None,
    ) -> None:
        super().__init__(aggregate_id, occurred_on, event_id, version)
        self._count = count

    def get_count(self) -> int:
        return self._count

    def _payload_dictionary(self) -> dict[str, Any]:
        return {"payload": {"count": self._count}}

    @classmethod
    def _from_payload_dictionary(cls, payload: dict[str, Any]) -> "FreeSpinRedeemedEvent":
        return cls(aggregate_id="pending", count=int(payload.get("count", 0)))


class WalletStatsEvent(AbstractWalletEvent):
    """Base for statistics-tracking events that do not alter the balance."""


class WageredRecordedEvent(WalletStatsEvent):
    """Emitted to record cumulative wager and win statistics."""

    EVENT_TYPE: ClassVar[str] = "WageredRecordedEvent"

    def __init__(
        self,
        aggregate_id: str,
        wager_amount: Money,
        win_amount: Money,
        game: str,
        occurred_on: Optional[datetime] = None,
        event_id: Optional[str] = None,
        version: Optional[AggregateVersion] = None,
    ) -> None:
        super().__init__(aggregate_id, occurred_on, event_id, version)
        self._wager_amount = wager_amount
        self._win_amount = win_amount
        self._game = game

    def get_wager_amount(self) -> Money:
        return self._wager_amount

    def get_win_amount(self) -> Money:
        return self._win_amount

    def get_game(self) -> str:
        return self._game

    def _payload_dictionary(self) -> dict[str, Any]:
        return {
            "payload": {
                "wager": self._wager_amount.to_decimal_string(),
                "win": self._win_amount.to_decimal_string(),
                "game": self._game,
            }
        }

    @classmethod
    def _from_payload_dictionary(cls, payload: dict[str, Any]) -> "WageredRecordedEvent":
        return cls(
            aggregate_id="pending",
            wager_amount=Money(payload.get("wager", "0")),
            win_amount=Money(payload.get("win", "0")),
            game=payload.get("game", ""),
        )


