"""
Leaderboard Query and Handler.

The leaderboard is exposed to the read side through a CQRS query. The query
handler answers it from the :class:`LeaderboardProjection` read model rather
than from the event store, keeping the read side fast and denormalized.
"""

from __future__ import annotations

from boombot.casino.application.bus.query_bus import AbstractQueryResult, IQueryHandler
from boombot.casino.reporting.domain.leaderboard import LeaderboardSnapshot
from boombot.casino.reporting.infrastructure.leaderboard_projection import (
    LeaderboardProjection,
)
from boombot.casino.shared.patterns import AbstractQuery


class GetLeaderboardQuery(AbstractQuery):
    """Request the top ``size`` player standings by balance."""

    def __init__(self, size: int) -> None:
        super().__init__()
        self._size = size

    def get_size(self) -> int:
        return self._size


class LeaderboardQueryResult(AbstractQueryResult):
    """The result of a leaderboard query."""

    def get_leaderboard(self) -> LeaderboardSnapshot:
        return self.get_payload()


class GetLeaderboardQueryHandler(IQueryHandler):
    """Answers :class:`GetLeaderboardQuery` from the projection read model."""

    def __init__(self, projection: LeaderboardProjection) -> None:
        self._projection = projection

    def handle(self, query: AbstractQuery) -> AbstractQueryResult:
        if not isinstance(query, GetLeaderboardQuery):
            raise TypeError(f"Unsupported query: {type(query).__name__}")
        snapshot = self._projection.get_leaderboard(query.get_size())
        return LeaderboardQueryResult(snapshot)