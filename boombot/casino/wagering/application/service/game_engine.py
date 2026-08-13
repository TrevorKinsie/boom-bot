"""
Game Engine Framework.

Game engines encapsulate the rules and outcomes of a single casino game. Each
engine is registered in the :class:`GameEngineRegistry` under a stable game
identifier so that the application service can dispatch gameplay actions
without an imperative chain of conditionals.

Engines are pure domain objects: they perform no I/O and no Telegram
interaction. They translate a gameplay action into a domain :class:`Outcome`
consumed by the application service.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

from boombot.casino.shared.exceptions import UnsupportedGameEngineException


class OutcomeKind:
    """Canonical outcome classifications."""
    WIN = "win"
    LOSS = "loss"
    PUSH = "push"


class Outcome:
    """Immutable representation of a single resolved wager."""

    def __init__(
        self,
        game: str,
        kind: str,
        wager: Any,
        winnings: Any,
        description: str = "",
    ) -> None:
        self._game = game
        self._kind = kind
        self._wager = wager
        self._winnings = winnings
        self._description = description

    def get_game(self) -> str:
        return self._game

    def get_kind(self) -> str:
        return self._kind

    def get_wager(self) -> Any:
        return self._wager

    def get_winnings(self) -> Any:
        return self._winnings

    def get_description(self) -> str:
        return self._description


class IGameEngine(ABC):
    """Port describing the capabilities of a casino game engine."""

    @abstractmethod
    def get_game_identifier(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def play(self, action: str, payload: dict[str, Any]) -> "GameOutcomeBundle":
        """Execute a gameplay action and produce a bundle of outcomes."""
        raise NotImplementedError


class GameOutcomeBundle:
    """Container for the results of a single gameplay action."""

    def __init__(
        self,
        summary: str,
        outcomes: list[Outcome],
        action_result: Any = None,
    ) -> None:
        self._summary = summary
        self._outcomes = outcomes
        self._action_result = action_result

    def get_summary(self) -> str:
        return self._summary

    def get_outcomes(self) -> list[Outcome]:
        return list(self._outcomes)

    def get_action_result(self) -> Any:
        return self._action_result


class GameEngineRegistry:
    """Registry resolving game engines by their stable identifier."""

    def __init__(self) -> None:
        self._engines: dict[str, IGameEngine] = {}
        self._factories: dict[str, Callable[[], IGameEngine]] = {}

    def register_engine(self, engine: IGameEngine) -> "GameEngineRegistry":
        self._engines[engine.get_game_identifier()] = engine
        return self

    def register_factory(
        self, game_identifier: str, factory: Callable[[], IGameEngine]
    ) -> "GameEngineRegistry":
        self._factories[game_identifier] = factory
        return self

    def resolve(self, game_identifier: str) -> IGameEngine:
        if game_identifier in self._engines:
            return self._engines[game_identifier]
        factory = self._factories.get(game_identifier)
        if factory is None:
            raise UnsupportedGameEngineException(
                f"No game engine registered for: {game_identifier}"
            )
        engine = factory()
        self._engines[game_identifier] = engine
        return engine

    def get_supported_games(self) -> list[str]:
        return sorted(set(self._engines) | set(self._factories))