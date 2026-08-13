"""
Wagering Queries.

Query objects describe read intentions within the wagering context. They never
mutate state; handlers answer them from projections or direct aggregate reads.
"""

from __future__ import annotations

from boombot.casino.shared.patterns import AbstractQuery


class GetWalletBalanceQuery(AbstractQuery):
    """Request the current balance and free spins of a user's wallet."""

    def __init__(self, user_id: str) -> None:
        super().__init__()
        self._user_id = user_id

    def get_user_id(self) -> str:
        return self._user_id


class GetWalletStatsQuery(AbstractQuery):
    """Request the cumulative wagering statistics of a user's wallet."""

    def __init__(self, user_id: str) -> None:
        super().__init__()
        self._user_id = user_id

    def get_user_id(self) -> str:
        return self._user_id