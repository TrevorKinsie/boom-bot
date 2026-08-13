"""
Game Session Store.

Active wagers and per-channel game state (such as the Craps point and phase)
are held in a session store scoped by tenant (channel) and game. The wallet
remains the single source of truth for money; the session store tracks only
the outstanding wagers that are pending resolution within a game round.

The in-memory implementation is safe within a single running process. A
persistent adapter can be substituted through the dependency injection
container without changing the application layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IGameSessionStore(ABC):
    """Port for the game session store."""

    @abstractmethod
    def get_channel_session(self, channel_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def save_channel_session(self, channel_id: str, session: dict[str, Any]) -> None:
        raise NotImplementedError


class InMemoryGameSessionStore(IGameSessionStore):
    """In-process implementation of the game session store."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    def get_channel_session(self, channel_id: str) -> dict[str, Any]:
        if channel_id not in self._sessions:
            self._sessions[channel_id] = {
                "roulette_bets": {},
                "craps_bets": {},
                "craps_state": 1,
                "craps_point": None,
            }
        return self._sessions[channel_id]

    def save_channel_session(self, channel_id: str, session: dict[str, Any]) -> None:
        self._sessions[channel_id] = session

    def clear(self) -> None:
        self._sessions.clear()