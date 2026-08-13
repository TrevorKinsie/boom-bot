"""
Dependency Injection Container.

The composition root of the casino platform. Every component is registered
against the interface (port) it implements and resolved at wiring time. The
container performs lazy singleton instantiation: the first resolution of a
registration constructs the instance, and every subsequent resolution returns
the same instance.

Registration keys are interface (class) objects; consumers request
dependencies by interface type, keeping the entire platform decoupled from
concrete implementations.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Type

logger = logging.getLogger(__name__)


class DependencyContainer:
    """A minimal, explicit service locator for the casino platform."""

    def __init__(self) -> None:
        self._factories: dict[Type[Any], Callable[["DependencyContainer"], Any]] = {}
        self._instances: dict[Type[Any], Any] = {}

    def register(
        self,
        contract: Type[Any],
        factory: Callable[["DependencyContainer"], Any],
        singleton: bool = True,
    ) -> "DependencyContainer":
        """Register a factory that produces an implementation of ``contract``."""
        if singleton:
            self._factories[contract] = factory
        else:
            self._factories[contract] = lambda container: factory(container)  # type: ignore[misc]
        return self

    def register_instance(
        self, contract: Type[Any], instance: Any
    ) -> "DependencyContainer":
        """Register a pre-constructed instance as a singleton."""
        self._instances[contract] = instance
        return self

    def resolve(self, contract: Type[Any]) -> Any:
        """Resolve an instance for ``contract``, constructing it on first use."""
        if contract in self._instances:
            return self._instances[contract]
        factory = self._factories.get(contract)
        if factory is None:
            raise KeyError(f"No registration found for contract: {contract.__name__}")
        instance = factory(self)
        if contract not in self._instances:
            self._instances[contract] = instance
        return instance

    def has_registration(self, contract: Type[Any]) -> bool:
        return contract in self._factories or contract in self._instances

    def resolve_many(self, *contracts: Type[Any]) -> list[Any]:
        return [self.resolve(contract) for contract in contracts]

    def shutdown(self) -> None:
        """Release lifecycle-managed resources (closable singletons)."""
        for instance in self._instances.values():
            closer = getattr(instance, "close", None)
            if callable(closer):
                try:
                    closer()
                except Exception as exc:  # noqa: BLE001 - best effort shutdown
                    logger.warning("Error closing %s: %s", type(instance).__name__, exc)
        self._instances.clear()