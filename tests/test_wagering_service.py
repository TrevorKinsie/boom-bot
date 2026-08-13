"""
Wagering Application Service Tests.

Validates the transactional use cases of the casino: roulette betting and
spinning, craps betting and rolling, zeus spins with free-spin logic, and
wallet reset. Each test uses an isolated in-memory session store and a fresh
temporary event store so balances never leak between tests.
"""

import pytest
from pathlib import Path

from boombot.casino.application.event.event_bus import InProcessEventBus, IEventBus
from boombot.casino.application.event.event_registry import (
    create_default_event_type_registry,
)
from boombot.casino.infrastructure.eventsourcing.event_store import SnapshotPolicy
from boombot.casino.infrastructure.eventsourcing.sqlite_event_store import (
    SqliteEventStoreAdapter,
)
from boombot.casino.shared.exceptions import (
    BetExceedsBalanceException,
    InvalidBetException,
)
from boombot.casino.shared.value_objects import Money
from boombot.casino.wagering.application.service.wagering_application_service import (
    WageringApplicationService,
)
from boombot.casino.wagering.infrastructure.persistence.game_session_store import (
    InMemoryGameSessionStore,
)
from boombot.casino.wagering.infrastructure.persistence.wallet_repository import (
    WalletRepository,
)


@pytest.fixture
def wagering_service(tmp_path):
    event_store = SqliteEventStoreAdapter(
        Path(tmp_path) / "casino.sqlite3", create_default_event_type_registry()
    )
    repository = WalletRepository(event_store, SnapshotPolicy(50), Money("100.00"))
    session_store = InMemoryGameSessionStore()
    event_bus = InProcessEventBus()
    service = WageringApplicationService(
        repository,
        event_bus,
        session_store,
        starting_balance=Money("100.00"),
        zeus_spin_cost=Money("10.00"),
    )
    return service, session_store


class TestRoulette:
    def test_place_and_spin(self, wagering_service):
        service, session = wagering_service
        service.place_roulette_bet("u1", "ch1", "red", "", "10.00")
        # Balance debited immediately.
        assert service.get_balance("u1").formatted() == "90.00"
        result = service.spin_roulette("ch1")
        assert result.startswith("The wheel landed on pocket")
        assert session.get_channel_session("ch1")["roulette_bets"] == {}

    def test_insufficient_funds_rejected(self, wagering_service):
        service, _ = wagering_service
        with pytest.raises(BetExceedsBalanceException):
            service.place_roulette_bet("u1", "ch1", "red", "", "500.00")

    def test_unsupported_bet_type_rejected(self, wagering_service):
        service, _ = wagering_service
        with pytest.raises(InvalidBetException):
            service.place_roulette_bet("u1", "ch1", "bogus", "", "10.00")


class TestCraps:
    def test_place_and_roll(self, wagering_service):
        service, session = wagering_service
        service.place_craps_bet("u1", "ch1", "pass_line", "10.00")
        assert service.get_balance("u1").formatted() == "90.00"
        result = service.roll_craps("ch1")
        assert result.startswith("Rolled")
        assert session.get_channel_session("ch1")["craps_bets"] == {}

    def test_unknown_bet_type_rejected(self, wagering_service):
        service, _ = wagering_service
        with pytest.raises(InvalidBetException):
            service.place_craps_bet("u1", "ch1", "bogus", "10.00")


class TestZeus:
    def test_spin_charges_and_credits(self, wagering_service):
        service, _ = wagering_service
        for _ in range(5):
            result = service.spin_zeus("u1")
            assert "Free spins" in result
        wallet = service.get_wallet("u1")
        # Every spin is either paid from balance or redeemed from free spins;
        # the balance may rise or fall depending on the grid outcome, but it
        # must remain a valid non-negative Money.
        assert wallet.get_games_played() >= 5
        assert service.get_balance("u1").amount() >= 0

    def test_spin_uses_free_spins_first(self, wagering_service):
        from boombot.casino.wagering.domain.model.wallet import Wallet

        service, _ = wagering_service
        wallet = service.get_wallet("u1")
        wallet.award_free_spins(1)
        service._flush(wallet)
        before = service.get_balance("u1")
        service.spin_zeus("u1")
        # A free spin should not have charged the balance.
        assert service.get_balance("u1").amount() >= before.amount()


class TestReset:
    def test_reset_wallet(self, wagering_service):
        service, _ = wagering_service
        service.place_roulette_bet("u1", "ch1", "red", "", "50.00")
        assert service.get_balance("u1").formatted() == "50.00"
        result = service.reset_wallet("u1")
        assert "reset to 100.00" in result
        assert service.get_balance("u1").formatted() == "100.00"