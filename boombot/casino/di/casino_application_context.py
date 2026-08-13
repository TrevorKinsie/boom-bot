"""
Casino Application Context (Composition Root).

The composition root is the single place where the entire casino platform is
wired together. It constructs the storage adapter (SQLite or JSON), the event
registry, repositories, the event bus with its read-model observers, the
wagering application service, and the CQRS buses with their registered
handlers.

Every dependency is registered against an interface contract and resolved
through :class:`DependencyContainer`, keeping each component decoupled from
its concrete collaborators.
"""

from __future__ import annotations

from pathlib import Path

from boombot.core.config import (
    CASINO_DEFAULT_STORAGE,
    CASINO_EVENT_STORE_JSON_FILE,
    CASINO_EVENT_STORE_SQLITE_FILE,
    CASINO_SNAPSHOT_THRESHOLD,
    CASINO_STARTING_BALANCE,
    ZEUS_SPIN_COST,
)
from boombot.casino.application.bus.command_bus import CommandBus
from boombot.casino.application.bus.query_bus import QueryBus
from boombot.casino.application.event.event_bus import IEventBus, InProcessEventBus
from boombot.casino.application.event.event_registry import (
    EventTypeRegistry,
    create_default_event_type_registry,
)
from boombot.casino.application.pipeline.middleware import (
    AuditTrailMiddleware,
    IdempotencyMiddleware,
    RetryMiddleware,
    TenantBindingMiddleware,
)
from boombot.casino.di.dependency_container import DependencyContainer
from boombot.casino.infrastructure.eventsourcing.event_store import IEventStore, SnapshotPolicy
from boombot.casino.infrastructure.eventsourcing.json_event_store import JsonEventStoreAdapter
from boombot.casino.infrastructure.eventsourcing.sqlite_event_store import SqliteEventStoreAdapter
from boombot.casino.multitenancy.tenant import ChatIdentifierTenantResolver, ITenantResolver
from boombot.casino.reporting.application.leaderboard_query import (
    GetLeaderboardQuery,
    GetLeaderboardQueryHandler,
)
from boombot.casino.reporting.infrastructure.leaderboard_projection import (
    LeaderboardProjection,
)
from boombot.casino.shared.value_objects import Money
from boombot.casino.wagering.application.bus_handlers import register_all_wagering_handlers
from boombot.casino.wagering.application.query.wallet_query_handlers import (
    GetWalletBalanceQueryHandler,
    GetWalletStatsQueryHandler,
)
from boombot.casino.wagering.application.query.wallet_queries import (
    GetWalletBalanceQuery,
    GetWalletStatsQuery,
)
from boombot.casino.wagering.application.service.wagering_application_service import (
    WageringApplicationService,
)
from boombot.casino.wagering.infrastructure.persistence.game_session_store import (
    IGameSessionStore,
    InMemoryGameSessionStore,
)
from boombot.casino.wagering.infrastructure.persistence.wallet_repository import (
    WalletRepository,
)


def _create_event_store(container: DependencyContainer) -> IEventStore:
    """Instantiate the configured event store adapter (SQLite or JSON)."""
    registry = container.resolve(EventTypeRegistry)
    if CASINO_DEFAULT_STORAGE == "json":
        return JsonEventStoreAdapter(Path(CASINO_EVENT_STORE_JSON_FILE), registry)
    return SqliteEventStoreAdapter(Path(CASINO_EVENT_STORE_SQLITE_FILE), registry)


def build_casino_container() -> DependencyContainer:
    """Construct and return the fully wired casino :class:`DependencyContainer`."""
    container = DependencyContainer()

    # --- Core infrastructure ---
    container.register_instance(EventTypeRegistry, create_default_event_type_registry())
    container.register(IEventStore, _create_event_store, singleton=True)
    container.register(
        SnapshotPolicy,
        lambda c: SnapshotPolicy(CASINO_SNAPSHOT_THRESHOLD),
        singleton=True,
    )
    container.register(
        IGameSessionStore, lambda c: InMemoryGameSessionStore(), singleton=True
    )
    container.register(
        ITenantResolver, lambda c: ChatIdentifierTenantResolver(), singleton=True
    )

    # --- Event bus + read-model observers ---
    container.register(IEventBus, lambda c: InProcessEventBus(), singleton=True)
    container.register(
        LeaderboardProjection, lambda c: LeaderboardProjection(), singleton=True
    )

    # --- Repositories ---
    container.register(
        WalletRepository,
        lambda c: WalletRepository(
            c.resolve(IEventStore),
            c.resolve(SnapshotPolicy),
            Money(CASINO_STARTING_BALANCE),
        ),
        singleton=True,
    )

    # --- Application service ---
    container.register(
        WageringApplicationService,
        lambda c: WageringApplicationService(
            c.resolve(WalletRepository),
            c.resolve(IEventBus),
            c.resolve(IGameSessionStore),
            starting_balance=Money(CASINO_STARTING_BALANCE),
            zeus_spin_cost=Money(ZEUS_SPIN_COST),
        ),
        singleton=True,
    )

    # --- CQRS buses ---
    container.register(CommandBus, lambda c: _build_command_bus(c), singleton=True)
    container.register(QueryBus, lambda c: _build_query_bus(c), singleton=True)

    # Register the leaderboard read-model observer on the event bus.
    event_bus = container.resolve(IEventBus)
    projection = container.resolve(LeaderboardProjection)
    event_bus.subscribe_all(projection)

    return container


def _build_command_bus(container: DependencyContainer) -> CommandBus:
    """Construct the command bus with pipeline middleware and handlers."""
    bus = CommandBus()
    bus.add_middleware(TenantBindingMiddleware())
    bus.add_middleware(IdempotencyMiddleware())
    bus.add_middleware(AuditTrailMiddleware())
    bus.add_middleware(RetryMiddleware())
    register_all_wagering_handlers(bus, container.resolve(WageringApplicationService))
    return bus


def _build_query_bus(container: DependencyContainer) -> QueryBus:
    """Construct the query bus with read-side handlers."""
    bus = QueryBus()
    service = container.resolve(WageringApplicationService)
    bus.register_handler(GetWalletBalanceQuery, GetWalletBalanceQueryHandler(service))
    bus.register_handler(GetWalletStatsQuery, GetWalletStatsQueryHandler(service))
    bus.register_handler(
        GetLeaderboardQuery,
        GetLeaderboardQueryHandler(container.resolve(LeaderboardProjection)),
    )
    return bus