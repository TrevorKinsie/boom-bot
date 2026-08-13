"""
Typed Exception Hierarchy.

Every failure mode of the casino platform is represented by a dedicated
exception type descending from :class:`CasinoException`. Callers and the
Telegram presentation layer may catch specific types and translate them into
friendly user-facing copy without resorting to broad exception handling.
"""

from __future__ import annotations


class CasinoException(Exception):
    """Base class for all casino platform exceptions."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self._message = message

    def get_message(self) -> str:
        return self._message


class InsufficientFundsException(CasinoException):
    """Raised when an operation would overdraw a wallet balance."""


class InvalidBetException(CasinoException):
    """Base class for invalid wager conditions."""


class NegativeBetAmountException(InvalidBetException):
    """Raised when a bet amount is not a positive monetary value."""


class BetExceedsBalanceException(InvalidBetException):
    """Raised when the requested wager surpasses the available balance."""


class UnknownBetTypeException(InvalidBetException):
    """Raised when an unsupported bet type identifier is supplied."""


class BetNotPermittedInPhaseException(InvalidBetException):
    """Raised when a bet type is not legal in the current game phase."""


class WalletNotFoundException(CasinoException):
    """Raised when no aggregate state can be located for a wallet identifier."""


class NegativeMonetaryAmountException(CasinoException):
    """Raised when a monetary value would violate its non-negative invariant."""


class PersistenceException(CasinoException):
    """Base class for persistence and event store failures."""


class JsonSerializationException(PersistenceException):
    """Raised when an aggregate cannot be serialized to its JSON form."""


class JsonDeserializationException(PersistenceException):
    """Raised when a persisted record cannot be deserialized."""


class ConcurrentModificationException(PersistenceException):
    """Raised when an optimistic-lock version conflict is detected."""


class UnsupportedStorageProviderException(PersistenceException):
    """Raised when an unknown storage provider is requested from the container."""


class UnsupportedGameEngineException(CasinoException):
    """Raised when a requested game engine is not registered in the registry."""


class CommandHandlerResolutionException(CasinoException):
    """Raised when no handler is registered for a command or query."""


class SagaExecutionException(CasinoException):
    """Raised when a saga step cannot be completed or compensated."""
