"""
Casino Dependency Container Tests.

Validates the composition root: that every component resolves, that the event
bus notifies the leaderboard projection, and that a complete wagering use case
round-trips through the command and query buses.
"""

import pytest

from boombot.casino.application.bus.command_bus import CommandBus
from boombot.casino.application.bus.query_bus import QueryBus
from boombot.casino.application.event.event_bus import IEventBus
from boombot.casino.decisionengine.application.decision_service import DecisionService
from boombot.casino.decisionengine.infrastructure.decision_engine_port import IDecisionEngine
from boombot.casino.decisionengine.infrastructure.jvm_decision_engine_gateway import (
    JvmDecisionEngineGateway,
)
from boombot.casino.di.casino_application_context import build_casino_container
from boombot.casino.infrastructure.eventsourcing.event_store import IEventStore
from boombot.casino.reporting.application.leaderboard_query import GetLeaderboardQuery
from boombot.casino.reporting.infrastructure.leaderboard_projection import (
    LeaderboardProjection,
)
from boombot.casino.wagering.application.command.wallet_commands import (
    PlaceRouletteBetCommand,
    ResetWalletCommand,
    SpinRouletteCommand,
    SpinZeusCommand,
)
from boombot.casino.wagering.application.query.wallet_queries import GetWalletBalanceQuery
from boombot.casino.wagering.application.service.wagering_application_service import (
    WageringApplicationService,
)
from boombot.casino.wagering.infrastructure.persistence.wallet_repository import (
    WalletRepository,
)


@pytest.fixture
def container():
    container = build_casino_container()
    yield container
    container.shutdown()


class TestCompositionRoot:
    def test_all_components_resolve(self, container):
        assert container.resolve(IEventStore) is not None
        assert container.resolve(WalletRepository) is not None
        assert container.resolve(WageringApplicationService) is not None
        assert container.resolve(CommandBus) is not None
        assert container.resolve(QueryBus) is not None
        assert container.resolve(IEventBus) is not None
        assert container.resolve(LeaderboardProjection) is not None
        assert container.resolve(IDecisionEngine) is not None
        assert container.resolve(JvmDecisionEngineGateway) is not None
        assert container.resolve(DecisionService) is not None

    def test_singletons_are_shared(self, container):
        assert container.resolve(IEventBus) is container.resolve(IEventBus)
        assert container.resolve(WageringApplicationService) is (
            container.resolve(WageringApplicationService)
        )

    def test_end_to_end_wagering_flow(self, container):
        command_bus = container.resolve(CommandBus)
        query_bus = container.resolve(QueryBus)

        command_bus.dispatch(PlaceRouletteBetCommand("u1", "ch1", "red", "", "25.00"))
        balance = query_bus.dispatch(GetWalletBalanceQuery("u1")).get_balance()
        assert balance.formatted() == "75.00"

        spin_result = command_bus.dispatch(SpinRouletteCommand("u1", "ch1"))
        assert spin_result.get_text().startswith("The wheel landed on pocket")

        zeus_result = command_bus.dispatch(SpinZeusCommand("u1"))
        assert "Free spins" in zeus_result.get_text()

        command_bus.dispatch(ResetWalletCommand("u1"))
        balance = query_bus.dispatch(GetWalletBalanceQuery("u1")).get_balance()
        assert balance.formatted() == "100.00"

        leaderboard = query_bus.dispatch(GetLeaderboardQuery(10)).get_leaderboard()
        assert leaderboard.get_size() >= 1

    def test_leaderboard_reflects_events(self, container):
        projection = container.resolve(LeaderboardProjection)
        command_bus = container.resolve(CommandBus)
        command_bus.dispatch(PlaceRouletteBetCommand("alice", "ch1", "red", "", "10.00"))
        command_bus.dispatch(SpinRouletteCommand("alice", "ch1"))
        standing = projection.get_standing("alice")
        assert standing is not None
        assert standing.get_games_played() == 1