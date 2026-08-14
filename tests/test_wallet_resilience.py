"""
Wallet Resilience & Bug-Fix Regression Tests.

These tests guard the specific defects discovered during the audit:

1. _advance_craps_phase returns a valid tuple on non-deciding rolls
   (the critical crash after a point is established).
2. IdempotencyMiddleware deduplicates retried commands when a command ID
   is assigned by the facade.
3. _flush survives a failing event subscriber without losing data.
4. SQLite store enforces optimistic concurrency on concurrent appends.
5. Wallet.from_state_dictionary survives null snapshot values.
6. Money rejects NaN and None with semantically correct messages.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from boombot.casino.application.bus.command_bus import (
    AbstractCommandResult,
    PipelineMiddleware,
)
from boombot.casino.application.event.domain_event import WalletCreatedEvent
from boombot.casino.application.event.event_bus import InProcessEventBus
from boombot.casino.application.event.event_registry import (
    create_default_event_type_registry,
)
from boombot.casino.application.pipeline.middleware import IdempotencyMiddleware
from boombot.casino.infrastructure.eventsourcing.event_store import SnapshotPolicy
from boombot.casino.infrastructure.eventsourcing.json_event_store import (
    JsonEventStoreAdapter,
)
from boombot.casino.infrastructure.eventsourcing.sqlite_event_store import (
    SqliteEventStoreAdapter,
)
from boombot.casino.shared.exceptions import (
    ConcurrentModificationException,
    NegativeMonetaryAmountException,
)
from boombot.casino.shared.value_objects import AggregateVersion, Money
from boombot.casino.wagering.application.command.wallet_commands import (
    AbstractWageringCommand,
)
from boombot.casino.wagering.application.service.wagering_application_service import (
    COME_OUT_PHASE,
    POINT_PHASE,
    WageringApplicationService,
)
from boombot.casino.wagering.infrastructure.persistence.game_session_store import (
    InMemoryGameSessionStore,
)
from boombot.casino.wagering.infrastructure.persistence.wallet_repository import (
    WalletRepository,
)


@pytest.fixture
def service_factory(tmp_path):
    """Return a callable that builds a WageringApplicationService with
    injectable dependencies."""
    def _build(event_bus=None, decision_service=None):
        event_store = SqliteEventStoreAdapter(
            Path(tmp_path) / "casino.sqlite3", create_default_event_type_registry()
        )
        repository = WalletRepository(
            event_store, SnapshotPolicy(50), Money("100.00")
        )
        session_store = InMemoryGameSessionStore()
        bus = event_bus or InProcessEventBus()
        return WageringApplicationService(
            repository, bus, session_store,
            starting_balance=Money("100.00"),
            zeus_spin_cost=Money("10.00"),
            decision_service=decision_service,
        )
    return _build


# ---------------------------------------------------------------------------
# 1. Craps phase advancement — the critical crash fix
# ---------------------------------------------------------------------------
class TestCrapsPhaseAdvancement:
    """Regression guard for the _advance_craps_phase fall-through crash."""

    def test_come_out_roll_establishes_point(self):
        """Come-out roll of 4-10 should return (POINT_PHASE, point_value)."""
        phase, point = WageringApplicationService._advance_craps_phase(8, None)
        assert phase == POINT_PHASE
        assert point == 8

    def test_come_out_roll_seven_or_eleven(self):
        """Come-out roll of 7 or 11 should return (COME_OUT_PHASE, None)."""
        for roll in (2, 3, 7, 11, 12):
            phase, point = WageringApplicationService._advance_craps_phase(roll, None)
            assert phase == COME_OUT_PHASE
            assert point is None

    def test_non_deciding_roll_after_point_keeps_point_phase(self):
        """The critical regression: a non-deciding roll after a point is
        established must NOT crash — it must return (POINT_PHASE, point)."""
        # Point is 8; roll a 5 (neither 8 nor 7)
        result = WageringApplicationService._advance_craps_phase(5, 8)
        assert result is not None  # would have been None before the fix
        phase, point = result
        assert phase == POINT_PHASE
        assert point == 8

    def test_seven_out_after_point(self):
        """Rolling a 7 after a point is established resets to come-out."""
        phase, point = WageringApplicationService._advance_craps_phase(7, 8)
        assert phase == COME_OUT_PHASE
        assert point is None

    def test_point_hit_after_point(self):
        """Rolling the point value again resets to come-out."""
        phase, point = WageringApplicationService._advance_craps_phase(8, 8)
        assert phase == COME_OUT_PHASE
        assert point is None

    def test_multi_roll_craps_does_not_crash(self, service_factory):
        """End-to-end: come-out -> point -> non-deciding roll -> resolve.

        Before the fix, the second roll (non-deciding) would raise:
          TypeError: cannot unpack non-iterable NoneType object
        """
        service = service_factory()
        # Mock the decision engine to produce deterministic dice:
        # (2,6)=8 point established, (3,2)=5 non-deciding, (4,4)=8 point hit
        with patch.object(
            service, "_decide_craps_roll",
            side_effect=[(2, 6), (3, 2), (4, 4)],
        ):
            # Come-out: pass_line bet
            service.place_craps_bet("u1", "ch1", "pass_line", "10.00")
            result1 = service.roll_craps("ch1")
            assert "Rolled 2 + 6 = 8." in result1

            # Point established (8): field bet is allowed in point phase
            service.place_craps_bet("u1", "ch1", "field", "10.00")
            result2 = service.roll_craps("ch1")
            assert "Rolled 3 + 2 = 5." in result2

            # Point hit: field bet again
            service.place_craps_bet("u1", "ch1", "field", "10.00")
            result3 = service.roll_craps("ch1")
            assert "Rolled 4 + 4 = 8." in result3


# ---------------------------------------------------------------------------
# 2. Idempotency middleware — deduplicates retried commands
# ---------------------------------------------------------------------------
class TestIdempotency:
    """Regression guard for idempotency middleware that was never activated."""

    def test_command_id_defaults_to_none(self):
        cmd = AbstractWageringCommand.__new__(AbstractWageringCommand)
        # AbstractCommand.__init__ sets _command_id = None
        AbstractWageringCommand.__init__(cmd, "u1", "ch1", "test")
        assert cmd.get_command_id() is None

    def test_assign_command_id_enables_dedup(self):
        cmd = AbstractWageringCommand.__new__(AbstractWageringCommand)
        AbstractWageringCommand.__init__(cmd, "u1", "ch1", "test")
        cmd.assign_command_id("u1:telegram")
        assert cmd.get_command_id() == "u1:telegram"

    def test_idempotency_middleware_rejects_duplicate(self):
        middleware = IdempotencyMiddleware()
        command_id = "u1:telegram:12345"

        cmd = MagicMock()
        cmd.get_command_id.return_value = command_id

        # First call delegates to invoke_next
        invoke_next = MagicMock()
        invoke_next.execute.return_value = AbstractCommandResult(success=True)
        result = middleware.handle(cmd, invoke_next)
        invoke_next.execute.assert_called_once()
        assert result.is_successful()

        # Second call with same ID is short-circuited
        invoke_next2 = MagicMock()
        invoke_next2.execute.return_value = AbstractCommandResult(success=True)
        result = middleware.handle(cmd, invoke_next2)
        invoke_next2.execute.assert_not_called()
        assert result.is_successful()

    def test_idempotency_middleware_passes_through_without_id(self):
        middleware = IdempotencyMiddleware()
        cmd = MagicMock()
        cmd.get_command_id.return_value = None

        invoke_next = MagicMock()
        invoke_next.execute.return_value = AbstractCommandResult(success=True)
        result = middleware.handle(cmd, invoke_next)
        invoke_next.execute.assert_called_once()
        assert result.is_successful()


# ---------------------------------------------------------------------------
# 3. _flush resilience — survives a failing event subscriber
# ---------------------------------------------------------------------------
class TestFlushResilience:
    """The _flush method should not crash if the event bus raises."""

    def test_flush_survives_event_bus_failure(self, service_factory):
        failing_bus = MagicMock()
        failing_bus.publish.side_effect = RuntimeError("subscriber exploded")
        service = service_factory(event_bus=failing_bus)

        # Provisioning triggers _flush; the event bus raises but should not crash
        service.get_wallet("u1")
        # Wallet is still retrievable from the persisted event store
        wallet = service.get_wallet("u1")
        assert wallet.get_balance().formatted() == "100.00"


# ---------------------------------------------------------------------------
# 4. SQLite optimistic concurrency
# ---------------------------------------------------------------------------
class TestOptimisticConcurrency:
    """The SQLite event store must reject concurrent writes that conflict
    on version."""

    def test_concurrent_append_raises_concurrent_modification(self, tmp_path):
        registry = create_default_event_type_registry()
        db_path = Path(tmp_path) / "casino.sqlite3"
        store_a = SqliteEventStoreAdapter(db_path, registry)
        store_b = SqliteEventStoreAdapter(db_path, registry)

        # Create wallet via store_a and persist initial event (version 1)
        repo_a = WalletRepository(store_a, SnapshotPolicy(50), Money("100.00"))
        wallet_a = repo_a.load_or_provision("u1")
        repo_a.save(wallet_a)  # commits version 1

        # Both stores now see the wallet at version 1
        repo_a2 = WalletRepository(store_a, SnapshotPolicy(50), Money("100.00"))
        wallet_a2 = repo_a2.load_or_provision("u1")
        repo_b2 = WalletRepository(store_b, SnapshotPolicy(50), Money("100.00"))
        wallet_b2 = repo_b2.load_or_provision("u1")

        # Both generate version 2 events (same starting version)
        wallet_a2.debit(Money("10.00"), "test")
        wallet_b2.debit(Money("5.00"), "test")

        # Store_a commits first (version 2)
        repo_a2.save(wallet_a2)

        # Store_b tries to commit version 2 — should raise because
        # store_a already committed version 2
        with pytest.raises(ConcurrentModificationException):
            repo_b2.save(wallet_b2)


# ---------------------------------------------------------------------------
# 5. Wallet.from_state_dictionary — null safety
# ---------------------------------------------------------------------------
class TestWalletSnapshotNullSafety:
    """from_state_dictionary must survive null values in snapshots."""

    def test_from_state_dictionary_handles_null_balance(self):
        from boombot.casino.wagering.domain.model.wallet import Wallet
        state = {"balance": None, "total_wagered": None, "total_won": None}
        wallet = Wallet.from_state_dictionary("u1", state)
        assert wallet.get_balance().formatted() == "0.00"
        assert wallet.get_total_wagered().formatted() == "0.00"
        assert wallet.get_total_won().formatted() == "0.00"

    def test_from_state_dictionary_handles_missing_keys(self):
        from boombot.casino.wagering.domain.model.wallet import Wallet
        wallet = Wallet.from_state_dictionary("u1", {})
        assert wallet.get_balance().formatted() == "0.00"


# ---------------------------------------------------------------------------
# 6. Money — NaN and None rejection
# ---------------------------------------------------------------------------
class TestMoneyValidation:
    def test_money_rejects_none(self):
        with pytest.raises(NegativeMonetaryAmountException, match="None"):
            Money(None)

    def test_money_rejects_nan(self):
        with pytest.raises(NegativeMonetaryAmountException, match="NaN"):
            Money(float("nan"))

    def test_money_rejects_negative(self):
        with pytest.raises(NegativeMonetaryAmountException, match="negative"):
            Money("-5.00")

    def test_money_rejects_non_numeric(self):
        with pytest.raises(NegativeMonetaryAmountException, match="non-numeric"):
            Money("not-a-number")

    def test_money_accepts_zero_string(self):
        assert Money("0").formatted() == "0.00"

    def test_money_accepts_zero_int(self):
        assert Money(0).formatted() == "0.00"


# ---------------------------------------------------------------------------
# 7. JSON event store — per-aggregate snapshot files
# ---------------------------------------------------------------------------
class TestJsonSnapshotIsolation:
    """Verifying that JSON snapshots use per-aggregate files, not a monolithic
    file that is read/written for every snapshot (the O(n) defect)."""

    def test_json_snapshot_per_aggregate(self, tmp_path):
        registry = create_default_event_type_registry()
        store = JsonEventStoreAdapter(
            Path(tmp_path) / "events.jsonl", registry
        )
        state_a = {"balance": "100.00"}
        state_b = {"balance": "200.00"}
        store.save_snapshot("u1", AggregateVersion(1), state_a)
        store.save_snapshot("u2", AggregateVersion(1), state_b)
        assert not (Path(tmp_path) / "events.snapshots.json").exists()
        snap_a = store.load_snapshot("u1")
        snap_b = store.load_snapshot("u2")
        assert snap_a is not None
        assert snap_b is not None
        assert snap_a[1]["balance"] == "100.00"
        assert snap_b[1]["balance"] == "200.00"


# ---------------------------------------------------------------------------
# 8. get_wallet — no double find on cold path
# ---------------------------------------------------------------------------
class TestGetWalletProvisioning:
    """get_wallet must provision a wallet in a single repository call."""

    def test_get_wallet_provisions_new_user_single_find(self, service_factory):
        service = service_factory()
        find_call_count = [0]
        original_find = service._wallet_repository.find

        def counting_find(uid):
            find_call_count[0] += 1
            return original_find(uid)

        service._wallet_repository.find = counting_find
        wallet = service.get_wallet("new_user")
        assert wallet.get_balance().formatted() == "100.00"
        assert find_call_count[0] == 1

    def test_get_wallet_existing_user_no_provision(self, service_factory):
        service = service_factory()
        service.get_wallet("u1")
        wallet = service.get_wallet("u1")
        assert wallet.get_balance().formatted() == "100.00"
        assert len(wallet.get_uncommitted_events()) == 0

