"""
Saga Framework (Process Manager).

A saga coordinates a multi-step flow that spans aggregate boundaries, with
compensating actions to roll back partial progress on failure. The coordinator
executes steps in order and, on any step failure, invokes compensation in
reverse order for every previously completed step.

Concrete sagas (for example :class:`BetLifecycleSaga`) implement the step list
and are executed through :class:`SagaCoordinator`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

TContext = TypeVar("TContext")


class SagaStep(ABC, Generic[TContext]):
    """A single step in a saga with a compensating action."""

    @abstractmethod
    def execute(self, context: TContext) -> None:
        raise NotImplementedError

    @abstractmethod
    def compensate(self, context: TContext) -> None:
        raise NotImplementedError

    def get_name(self) -> str:
        return self.__class__.__name__


class Saga(ABC, Generic[TContext]):
    """A choreographed workflow composed of ordered saga steps."""

    @abstractmethod
    def get_steps(self) -> list[SagaStep[TContext]]:
        raise NotImplementedError


class SagaCoordinator:
    """Executes a saga, compensating completed steps on failure."""

    def __init__(self, logger: Any = None) -> None:
        import logging

        self._logger = logger or logging.getLogger(__name__)

    def execute(self, saga: Saga, context: Any) -> Any:
        completed: list[SagaStep] = []
        try:
            for step in saga.get_steps():
                self._logger.info("SAGA step begin=%s", step.get_name())
                step.execute(context)
                completed.append(step)
                self._logger.info("SAGA step complete=%s", step.get_name())
        except Exception as exc:
            self._logger.warning("SAGA failure at %s, compensating (%s steps)",
                                 completed[-1].get_name() if completed else "start",
                                 len(completed))
            for step in reversed(completed):
                try:
                    step.compensate(context)
                except Exception as comp_exc:  # noqa: BLE001
                    self._logger.error("SAGA compensation failed for %s: %s",
                                       step.get_name(), comp_exc)
            raise
        return context