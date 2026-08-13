"""
Leaderboard Projection Tests.

Validates the read-model projection of wallet events and the CQRS leaderboard
query handler.
"""

from boombot.casino.application.event.domain_event import (
    FundsCreditedEvent,
    FundsDebitedEvent,
    WalletCreatedEvent,
    WageredRecordedEvent,
)
from boombot.casino.application.event.event_bus import InProcessEventBus
from boombot.casino.reporting.application.leaderboard_query import (
    GetLeaderboardQuery,
    GetLeaderboardQueryHandler,
)
from boombot.casino.reporting.infrastructure.leaderboard_projection import (
    LeaderboardProjection,
)
from boombot.casino.shared.value_objects import Money


class TestLeaderboardProjection:
    def test_folds_wallet_events(self):
        projection = LeaderboardProjection()
        projection.register_name("u1", "Alice")
        projection.register_name("u2", "Bob")
        projection.notify(WalletCreatedEvent("u1", Money("100.00")))
        projection.notify(WalletCreatedEvent("u2", Money("100.00")))
        projection.notify(FundsDebitedEvent("u1", Money("20.00"), "craps"))
        projection.notify(FundsCreditedEvent("u2", Money("50.00"), "zeus"))
        projection.notify(WageredRecordedEvent("u2", Money("10.00"), Money("50.00"), "zeus"))

        snapshot = projection.get_leaderboard(10)
        rankings = snapshot.get_rankings()
        assert len(rankings) == 2
        # Bob (150) ranks above Alice (80).
        assert rankings[0].get_display_name() == "Bob"
        assert rankings[0].get_balance().formatted() == "150.00"
        assert rankings[1].get_display_name() == "Alice"
        assert rankings[1].get_balance().formatted() == "80.00"

    def test_query_handler_answers_from_projection(self):
        projection = LeaderboardProjection()
        projection.register_name("u1", "Alice")
        projection.notify(WalletCreatedEvent("u1", Money("100.00")))
        handler = GetLeaderboardQueryHandler(projection)
        result = handler.handle(GetLeaderboardQuery(10))
        assert result.get_leaderboard().get_size() == 1


class TestEventBusObserverWiring:
    def test_projection_receives_published_events(self):
        bus = InProcessEventBus()
        projection = LeaderboardProjection()
        bus.subscribe_all(projection)
        bus.publish(WalletCreatedEvent("u1", Money("100.00")))
        bus.publish(FundsDebitedEvent("u1", Money("10.00"), "roulette"))
        standing = projection.get_standing("u1")
        assert standing is not None
        assert standing.get_balance().formatted() == "90.00"