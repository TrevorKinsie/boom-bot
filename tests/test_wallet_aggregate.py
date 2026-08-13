"""
Wallet Aggregate and Event Store Tests.

Validates the event-sourced wallet aggregate: state transitions, invariant
enforcement, persistence round-trips through both the SQLite and JSON event
store adapters, snapshot-aware reconstruction, and ledger statistics.
"""

import pytest
from pathlib import Path

from boombot.casino.application.event.event_registry import (
    EventTypeRegistry,
    create_default_event_type_registry,
)
from boombot.casino.infrastructure.eventsourcing.event_store import SnapshotPolicy
from boombot.casino.infrastructure.eventsourcing.json_event_store import (
    JsonEventStoreAdapter,
)
from boombot.casino.infrastructure.eventsourcing.sqlite_event_store import (
    SqliteEventStoreAdapter,
)
from boombot.casino.shared.exceptions import InsufficientFundsException
from boombot.casino.shared.value_objects import Money
from boombot.casino.wagering.domain.model.wallet import Wallet
from boombot.casino.wagering.infrastructure.persistence.wallet_repository import (
    WalletRepository,
)


@pytest.fixture
def event_registry() -> EventTypeRegistry:
    return create_default_event_type_registry()


def _repository_for(store):
    return WalletRepository(store, SnapshotPolicy(5), Money("100.00"))


class TestWalletAggregate:
    def test_provision_grants_starting_balance(self):
        wallet = Wallet("u1")
        wallet.provision(Money("100.00"))
        assert wallet.get_balance().formatted() == "100.00"

    def test_debit_credits_update_balance(self):
        wallet = Wallet("u1")
        wallet.provision(Money("100.00"))
        wallet.debit(Money("30.00"), "roulette")
        assert wallet.get_balance().formatted() == "70.00"
        wallet.credit(Money("10.00"), "payout")
        assert wallet.get_balance().formatted() == "80.00"

    def test_debit_rejects_overdraw(self):
        wallet = Wallet("u1")
        wallet.provision(Money("10.00"))
        with pytest.raises(InsufficientFundsException):
            wallet.debit(Money("20.00"), "craps")

    def test_free_spins_tracking(self):
        wallet = Wallet("u1")
        wallet.provision(Money("100.00"))
        wallet.award_free_spins(2)
        wallet.redeem_free_spin()
        assert wallet.get_free_spins() == 1
        with pytest.raises(InsufficientFundsException):
            wallet.redeem_free_spin()
            wallet.redeem_free_spin()

    def test_stats_recorded(self):
        wallet = Wallet("u1")
        wallet.provision(Money("100.00"))
        wallet.record_wager(Money("10.00"), Money("30.00"), "craps")
        wallet.record_wager(Money("5.00"), Money("2.00"), "roulette")
        assert wallet.get_total_wagered().formatted() == "15.00"
        assert wallet.get_total_won().formatted() == "32.00"
        assert wallet.get_biggest_win().formatted() == "30.00"
        assert wallet.get_games_played() == 2

    def test_replay_reconstructs_state(self):
        wallet = Wallet("u1")
        wallet.provision(Money("100.00"))
        wallet.debit(Money("10.00"), "craps")
        events = wallet.get_uncommitted_events()
        rebuilt = Wallet("u1")
        rebuilt.replay(events)
        assert rebuilt.get_balance().formatted() == "90.00"


@pytest.mark.parametrize(
    "store_factory",
    [
        lambda td, registry: SqliteEventStoreAdapter(
            Path(td) / "casino.sqlite3", registry
        ),
        lambda td, registry: JsonEventStoreAdapter(
            Path(td) / "casino_events.jsonl", registry
        ),
    ],
    ids=["sqlite", "json"],
)
class TestEventStoreRoundTrip:
    def test_wallet_round_trip(self, tmp_path, event_registry, store_factory):
        store = store_factory(tmp_path, event_registry)
        repository = _repository_for(store)
        try:
            wallet = repository.load_or_provision("u1")
            wallet.debit(Money("10.00"), "craps")
            wallet.credit(Money("20.00"), "payout")
            wallet.award_free_spins(1)
            wallet.record_wager(Money("10.00"), Money("20.00"), "craps")
            repository.save(wallet)

            reloaded = repository.find("u1")
            assert reloaded is not None
            assert reloaded.get_balance().formatted() == "110.00"
            assert reloaded.get_free_spins() == 1
            assert reloaded.get_total_won().formatted() == "20.00"
            assert reloaded.get_games_played() == 1
        finally:
            store.close()

    def test_snapshot_reconstruction(self, tmp_path, event_registry, store_factory):
        store = store_factory(tmp_path, event_registry)
        repository = WalletRepository(store, SnapshotPolicy(3), Money("100.00"))
        try:
            wallet = repository.load_or_provision("u1")
            for _ in range(5):
                wallet.debit(Money("1.00"), "test")
                repository.save(wallet)
            snapshot = store.load_snapshot("u1")
            assert snapshot is not None
            reloaded = repository.find("u1")
            assert reloaded.get_balance().formatted() == "95.00"
        finally:
            store.close()