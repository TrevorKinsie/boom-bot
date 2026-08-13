"""
Leaderboard Projection.

A read-model projection that subscribes to the in-process event bus and folds
wallet domain events into an in-memory denormalized table of player standings.
The projection is an :class:`IGameObserver`: it is notified for every wallet
event and updates its internal state accordingly.

Display names are supplied by the presentation layer via :meth:`register_name`
because wallet events do not carry identity metadata.
"""

from __future__ import annotations

from boombot.casino.application.event.domain_event import (
    AbstractDomainEvent,
    FundsCreditedEvent,
    FundsDebitedEvent,
    WalletCreatedEvent,
    WalletResetEvent,
    WageredRecordedEvent,
)
from boombot.casino.application.event.event_bus import IGameObserver
from boombot.casino.reporting.domain.leaderboard import (
    LeaderboardSnapshot,
    PlayerStanding,
)
from boombot.casino.shared.value_objects import Money


class LeaderboardProjection(IGameObserver):
    """Projects wallet events into a leaderboard read model."""

    def __init__(self) -> None:
        self._standings: dict[str, PlayerStanding] = {}
        self._display_names: dict[str, str] = {}

    def register_name(self, user_id: str, display_name: str) -> None:
        self._display_names[user_id] = display_name

    def notify(self, event: AbstractDomainEvent) -> None:
        if not isinstance(
            event,
            (WalletCreatedEvent, FundsDebitedEvent, FundsCreditedEvent, WalletResetEvent, WageredRecordedEvent),
        ):
            return
        user_id = event.get_aggregate_id()
        current = self._standings.get(user_id)
        balance = current.get_balance() if current else Money.zero()
        total_won = current.get_total_won() if current else Money.zero()
        total_wagered = current.get_total_wagered() if current else Money.zero()
        games_played = current.get_games_played() if current else 0

        if isinstance(event, WalletCreatedEvent):
            balance = event.get_starting_balance()
        elif isinstance(event, FundsDebitedEvent):
            balance = balance.subtract(event.get_amount())
        elif isinstance(event, FundsCreditedEvent):
            balance = balance.add(event.get_amount())
        elif isinstance(event, WalletResetEvent):
            balance = event.get_reset_balance()
        elif isinstance(event, WageredRecordedEvent):
            total_wagered = total_wagered.add(event.get_wager_amount())
            total_won = total_won.add(event.get_win_amount())
            games_played += 1

        self._standings[user_id] = PlayerStanding(
            user_id=user_id,
            display_name=self._display_names.get(user_id, user_id),
            balance=balance,
            total_won=total_won,
            total_wagered=total_wagered,
            games_played=games_played,
        )

    def get_leaderboard(self, size: int) -> LeaderboardSnapshot:
        ranked = sorted(
            self._standings.values(),
            key=lambda standing: standing.get_balance().amount(),
            reverse=True,
        )
        return LeaderboardSnapshot(ranked[:size])

    def get_standing(self, user_id: str) -> PlayerStanding | None:
        return self._standings.get(user_id)

    def clear(self) -> None:
        self._standings.clear()
        self._display_names.clear()