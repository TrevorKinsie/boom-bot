"""
Wallet Query Handlers.

Query handlers answer read intentions from the wagering context without
mutating state. They delegate to the application service's wallet accessors
and return typed query results for presentation.
"""

from __future__ import annotations

from typing import Any

from boombot.casino.application.bus.query_bus import AbstractQueryResult, IQueryHandler
from boombot.casino.shared.patterns import AbstractQuery
from boombot.casino.wagering.application.query.wallet_queries import (
    GetWalletBalanceQuery,
    GetWalletStatsQuery,
)
from boombot.casino.wagering.application.service.wagering_application_service import (
    WageringApplicationService,
)


class WalletBalanceQueryResult(AbstractQueryResult):
    """Result of a wallet balance query."""

    def get_balance(self) -> Any:
        return self.get_payload().get("balance")

    def get_free_spins(self) -> int:
        return int(self.get_payload().get("free_spins", 0))


class GetWalletBalanceQueryHandler(IQueryHandler):
    """Answers :class:`GetWalletBalanceQuery` via the application service."""

    def __init__(self, application_service: WageringApplicationService) -> None:
        self._application_service = application_service

    def handle(self, query: AbstractQuery) -> AbstractQueryResult:
        if not isinstance(query, GetWalletBalanceQuery):
            raise TypeError(f"Unsupported query: {type(query).__name__}")
        stats = self._application_service.get_stats(query.get_user_id())
        return WalletBalanceQueryResult(
            {
                "balance": stats["balance"],
                "free_spins": stats["free_spins"],
            }
        )


class GetWalletStatsQueryHandler(IQueryHandler):
    """Answers :class:`GetWalletStatsQuery` via the application service."""

    def __init__(self, application_service: WageringApplicationService) -> None:
        self._application_service = application_service

    def handle(self, query: AbstractQuery) -> AbstractQueryResult:
        if not isinstance(query, GetWalletStatsQuery):
            raise TypeError(f"Unsupported query: {type(query).__name__}")
        stats = self._application_service.get_stats(query.get_user_id())
        return AbstractQueryResult(stats)