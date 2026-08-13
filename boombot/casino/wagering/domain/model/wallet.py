"""
Wallet Aggregate.

The Wallet is the central aggregate root of the wagering context. It owns the
player's monetary balance, cumulative wagering statistics, and free-spin
entitlements. Because the platform is event-sourced, the Wallet never mutates
a stored balance directly; every state transition is expressed as a domain
event that is applied to the aggregate and later appended to the event store.

Invariants enforced by this aggregate:

* A debit may never overdraw the balance (:class:`InsufficientFundsException`).
* All monetary values are non-negative :class:`Money` objects.
* Free spins may never be redeemed below zero.
"""

from __future__ import annotations

from typing import Any, Optional

from boombot.casino.application.event.domain_event import (
    AbstractDomainEvent,
    AbstractWalletEvent,
    WalletCreatedEvent,
    FundsDebitedEvent,
    FundsCreditedEvent,
    WalletResetEvent,
    FreeSpinAwardedEvent,
    FreeSpinRedeemedEvent,
    WageredRecordedEvent,
)
from boombot.casino.infrastructure.eventsourcing.abstract_event_sourced_aggregate import (
    AbstractEventSourcedAggregate,
)
from boombot.casino.shared.exceptions import InsufficientFundsException
from boombot.casino.shared.value_objects import Money, AggregateVersion


class Wallet(AbstractEventSourcedAggregate):
    """An event-sourced monetary aggregate for a single player."""

    def __init__(
        self,
        identity: str,
        version: AggregateVersion | None = None,
        created_by: Optional[str] = None,
    ) -> None:
        super().__init__(identity, version, created_by)
        self._balance: Money = Money.zero()
        self._total_wagered: Money = Money.zero()
        self._total_won: Money = Money.zero()
        self._biggest_win: Money = Money.zero()
        self._free_spins: int = 0
        self._games_played: int = 0

    # --- Query accessors ---
    def get_balance(self) -> Money:
        return self._balance

    def get_total_wagered(self) -> Money:
        return self._total_wagered

    def get_total_won(self) -> Money:
        return self._total_won

    def get_biggest_win(self) -> Money:
        return self._biggest_win

    def get_free_spins(self) -> int:
        return self._free_spins

    def get_games_played(self) -> int:
        return self._games_played

    # --- Command / mutation operations ---
    def provision(self, starting_balance: Money) -> None:
        """Provision a brand-new wallet with the platform starting balance."""
        self.raise_event(WalletCreatedEvent(self.get_identity(), starting_balance))

    def debit(self, amount: Money, reason: str) -> None:
        """Reserve funds from the wallet, rejecting an overdraw."""
        if amount.is_zero():
            return
        if amount.is_greater_than(self._balance):
            raise InsufficientFundsException(
                f"Insufficient funds: balance {self._balance.formatted()} "
                f"cannot cover debit {amount.formatted()}."
            )
        self.raise_event(FundsDebitedEvent(self.get_identity(), amount, reason))

    def credit(self, amount: Money, reason: str) -> None:
        """Return funds to the wallet (e.g. a payout)."""
        if amount.is_zero():
            return
        self.raise_event(FundsCreditedEvent(self.get_identity(), amount, reason))

    def reset(self, reset_balance: Money) -> None:
        """Restore the wallet balance to the configured starting amount."""
        self.raise_event(WalletResetEvent(self.get_identity(), reset_balance))

    def award_free_spins(self, count: int) -> None:
        if count <= 0:
            return
        self.raise_event(FreeSpinAwardedEvent(self.get_identity(), count))

    def redeem_free_spin(self) -> None:
        if self._free_spins <= 0:
            raise InsufficientFundsException("No free spins are available to redeem.")
        self.raise_event(FreeSpinRedeemedEvent(self.get_identity(), 1))

    def record_wager(self, wager: Money, win: Money, game: str) -> None:
        """Record cumulative wagering statistics without touching the balance."""
        self.raise_event(WageredRecordedEvent(self.get_identity(), wager, win, game))

    # --- Event application (write-model fold) ---
    def apply(self, event: AbstractDomainEvent) -> None:
        if not isinstance(event, AbstractWalletEvent):
            raise TypeError(f"Wallet cannot apply event: {event.event_type()}")
        if isinstance(event, WalletCreatedEvent):
            self._balance = event.get_starting_balance()
        elif isinstance(event, FundsDebitedEvent):
            self._balance = self._balance.subtract(event.get_amount())
        elif isinstance(event, FundsCreditedEvent):
            self._balance = self._balance.add(event.get_amount())
        elif isinstance(event, WalletResetEvent):
            self._balance = event.get_reset_balance()
        elif isinstance(event, FreeSpinAwardedEvent):
            self._free_spins += event.get_count()
        elif isinstance(event, FreeSpinRedeemedEvent):
            self._free_spins = max(0, self._free_spins - event.get_count())
        elif isinstance(event, WageredRecordedEvent):
            self._total_wagered = self._total_wagered.add(event.get_wager_amount())
            self._total_won = self._total_won.add(event.get_win_amount())
            self._games_played += 1
            if event.get_win_amount().is_greater_than(self._biggest_win):
                self._biggest_win = event.get_win_amount()
        else:
            raise TypeError(f"Unhandled wallet event type: {event.event_type()}")

    # --- Snapshot / serialization ---
    def to_state_dictionary(self) -> dict[str, Any]:
        return {
            "balance": self._balance.to_decimal_string(),
            "total_wagered": self._total_wagered.to_decimal_string(),
            "total_won": self._total_won.to_decimal_string(),
            "biggest_win": self._biggest_win.to_decimal_string(),
            "free_spins": self._free_spins,
            "games_played": self._games_played,
        }

    @classmethod
    def from_state_dictionary(cls, identity: str, state: dict[str, Any]) -> "Wallet":
        wallet = cls(identity)
        wallet._balance = Money(state.get("balance", "0"))
        wallet._total_wagered = Money(state.get("total_wagered", "0"))
        wallet._total_won = Money(state.get("total_won", "0"))
        wallet._biggest_win = Money(state.get("biggest_win", "0"))
        wallet._free_spins = int(state.get("free_spins", 0))
        wallet._games_played = int(state.get("games_played", 0))
        return wallet
