"""
Wallet Repository.

The persistence adapter for the :class:`Wallet` aggregate. It is responsible
for materializing a wallet from its event stream (optionally seeded from a
compacted snapshot) and for persisting staged uncommitted events as an atomic
append batch, applying the snapshot policy to bound replay cost.
"""

from __future__ import annotations

from typing import Optional

from boombot.casino.infrastructure.eventsourcing.abstract_event_sourced_aggregate import (
    AbstractEventSourcedAggregate,
)
from boombot.casino.infrastructure.eventsourcing.event_store import (
    IEventStore,
    SnapshotPolicy,
)
from boombot.casino.shared.value_objects import Money
from boombot.casino.wagering.domain.model.wallet import Wallet


class WalletRepository:
    """Repository that reconstructs and persists :class:`Wallet` aggregates."""

    def __init__(
        self,
        event_store: IEventStore,
        snapshot_policy: SnapshotPolicy,
        starting_balance: Money | None = None,
    ) -> None:
        self._event_store = event_store
        self._snapshot_policy = snapshot_policy
        self._starting_balance = starting_balance or Money("100.00")

    def get_starting_balance(self) -> Money:
        return self._starting_balance

    def find(self, user_id: str) -> Optional[Wallet]:
        """Load a wallet from snapshot + event replay, or None if absent."""
        snapshot = self._event_store.load_snapshot(user_id)
        if snapshot is not None:
            snapshot_version, snapshot_state = snapshot
            wallet = Wallet.from_snapshot_state(user_id, snapshot_state)
            rest = self._event_store.load(user_id)
            replay_events = [e for e in rest if e.get_version().number() > snapshot_version.number()]
        else:
            wallet = Wallet(user_id)
            replay_events = self._event_store.load(user_id)
        if not replay_events and wallet.get_version().number() == 0:
            return None
        if replay_events:
            wallet.replay(replay_events)
        return wallet

    def load_or_provision(self, user_id: str) -> Wallet:
        """Return the wallet for a user, provisioning a new one if absent."""
        existing = self.find(user_id)
        if existing is not None:
            return existing
        wallet = Wallet(user_id)
        wallet.provision(self._starting_balance)
        return wallet

    def save(self, wallet: AbstractEventSourcedAggregate) -> None:
        """Persist any staged events and apply the snapshot policy."""
        committed_version = wallet.get_version().number() - len(wallet.get_uncommitted_events())
        uncommitted = wallet.get_uncommitted_events()
        if not uncommitted:
            return
        self._event_store.append(wallet.get_identity(), uncommitted)
        if self._snapshot_policy.should_take_snapshot(
            len(uncommitted), committed_version
        ):
            self._event_store.save_snapshot(
                wallet.get_identity(),
                wallet.get_version(),
                wallet.to_snapshot_state(),
            )
        wallet.commit()
