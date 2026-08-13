"""
Leaderboard Reporting Domain.

The reporting context consumes wallet domain events and maintains a
denormalized read model of player standings for the leaderboard. The read
model is expressed as immutable value objects produced by the projection.
"""

from __future__ import annotations

from typing import Any

from boombot.casino.shared.value_objects import Money


class PlayerStanding:
    """Immutable snapshot of a single player's cumulative standing."""

    __slots__ = (
        "_user_id",
        "_display_name",
        "_balance",
        "_total_won",
        "_total_wagered",
        "_games_played",
    )

    def __init__(
        self,
        user_id: str,
        display_name: str,
        balance: Money,
        total_won: Money,
        total_wagered: Money,
        games_played: int,
    ) -> None:
        self._user_id = user_id
        self._display_name = display_name
        self._balance = balance
        self._total_won = total_won
        self._total_wagered = total_wagered
        self._games_played = games_played

    def get_user_id(self) -> str:
        return self._user_id

    def get_display_name(self) -> str:
        return self._display_name

    def get_balance(self) -> Money:
        return self._balance

    def get_total_won(self) -> Money:
        return self._total_won

    def get_total_wagered(self) -> Money:
        return self._total_wagered

    def get_games_played(self) -> int:
        return self._games_played

    def to_dictionary(self) -> dict[str, Any]:
        return {
            "user_id": self._user_id,
            "display_name": self._display_name,
            "balance": self._balance.to_decimal_string(),
            "total_won": self._total_won.to_decimal_string(),
            "total_wagered": self._total_wagered.to_decimal_string(),
            "games_played": self._games_played,
        }


class LeaderboardSnapshot:
    """Immutable, ordered snapshot of the top player standings."""

    __slots__ = ("_rankings", "_generated_at")

    def __init__(self, rankings: list[PlayerStanding]) -> None:
        from datetime import datetime, timezone

        self._rankings = list(rankings)
        self._generated_at = datetime.now(timezone.utc)

    def get_rankings(self) -> list[PlayerStanding]:
        return list(self._rankings)

    def get_size(self) -> int:
        return len(self._rankings)

    def get_generated_at(self) -> Any:
        return self._generated_at