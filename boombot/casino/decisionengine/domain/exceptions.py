"""Decision domain exceptions.

Distinct failure modes of the decision fabric. These are *internal* signals
used by the application layer to degrade gracefully to the reference
implementation; they are deliberately not ``CasinoException`` subtypes so the
Telegram facade keeps treating them as engine-internal concerns rather than
player-facing error messages.
"""
from __future__ import annotations


class DecisionEngineException(Exception):
    """Base class for all decision-engine failures."""


class DecisionEngineUnavailableException(DecisionEngineException):
    """Raised when no JVM decision engine can be reached (missing jar/launcher)."""


class DecisionEngineFailureException(DecisionEngineException):
    """Raised when the JVM decision engine rejects or fails a request."""