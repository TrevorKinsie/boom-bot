"""
Query Bus (read side of CQRS).

Queries describe a read intention and never mutate state. They are dispatched
to a registered query handler which typically reads from a denormalized
projection rather than the event store itself. Each query produces an
:class:`AbstractQueryResult`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Type

from boombot.casino.shared.exceptions import CommandHandlerResolutionException
from boombot.casino.shared.patterns import AbstractQuery


class AbstractQueryResult:
    """Marker base class for the result produced by a query handler."""

    def __init__(self, payload: Any = None) -> None:
        self._payload = payload

    def get_payload(self) -> Any:
        return self._payload


class IQueryHandler(ABC):
    """Port for a handler that answers a single query type."""

    @abstractmethod
    def handle(self, query: AbstractQuery) -> AbstractQueryResult:
        raise NotImplementedError


class IQueryBus(ABC):
    """Port describing query dispatch."""

    @abstractmethod
    def dispatch(self, query: AbstractQuery) -> AbstractQueryResult:
        raise NotImplementedError


class QueryBus(IQueryBus):
    """Resolves the registered handler for a query and dispatches it."""

    def __init__(self) -> None:
        self._handlers: dict[Type[AbstractQuery], IQueryHandler] = {}

    def register_handler(
        self, query_type: Type[AbstractQuery], handler: IQueryHandler
    ) -> "QueryBus":
        self._handlers[query_type] = handler
        return self

    def dispatch(self, query: AbstractQuery) -> AbstractQueryResult:
        handler = self._handlers.get(type(query))
        if handler is None:
            raise CommandHandlerResolutionException(
                f"No query handler registered for: {type(query).__name__}"
            )
        return handler.handle(query)