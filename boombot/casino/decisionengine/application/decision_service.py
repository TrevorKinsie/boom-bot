"""Decision Service.

The application orchestrator of the decision fabric. It:

* derives a reproducible seed for each decision from its context,
* builds a :class:`DecisionRequest`,
* routes it through the primary provider (the JVM engine when available),
* transparently degrades to the reference implementation when the JVM engine
  is unavailable or fails, and
* validates the rendered decision against its family output specification.

The service is the only object the wagering application service talks to, so
the application layer never depends on whether a decision came from Rust, the
JVM, or Python's :mod:`random`.
"""
from __future__ import annotations

import hashlib
import itertools
import logging
import time
from typing import Any, Mapping

from boombot.casino.decisionengine.domain.decision import Decision, DecisionKind, DecisionRequest
from boombot.casino.decisionengine.domain.decision_specifications import validate_decision
from boombot.casino.decisionengine.domain.exceptions import DecisionEngineException
from boombot.casino.decisionengine.infrastructure.decision_engine_port import IDecisionEngine
from boombot.casino.decisionengine.infrastructure.reference_decision_engine import (
    ReferenceDecisionEngine,
)

logger = logging.getLogger(__name__)


class DecisionService:
    """Orchestrates decision requests across a primary and fallback provider."""

    def __init__(
        self,
        primary: IDecisionEngine,
        fallback: IDecisionEngine | None = None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback or ReferenceDecisionEngine()
        self._counter = itertools.count(1)

    def decide(
        self,
        kind: DecisionKind,
        context: Mapping[str, Any] | None = None,
    ) -> Decision:
        """Render a single decision, degrading to the reference provider as needed."""
        seed = self._derive_seed(context)
        request = DecisionRequest(kind=kind, seed=seed, context=context)
        decision = self._route(request)
        validate_decision(decision)
        return decision

    def fairness_hash(self, context: Mapping[str, Any] | None = None) -> str:
        """Compute a reproducible fairness hash for a derived seed (audit hook)."""
        seed = self._derive_seed(context)
        decision = self._route(DecisionRequest(DecisionKind.FAIRNESS_HASH, seed, context))
        return str(decision.get("hash"))

    def is_fabric_active(self) -> bool:
        """Return whether the primary (JVM) provider is currently engaged."""
        return self._primary.is_available()

    def _route(self, request: DecisionRequest) -> Decision:
        if self._primary.is_available():
            try:
                return self._primary.decide(request)
            except DecisionEngineException as exc:
                logger.warning(
                    "Primary decision engine failed (%s); degrading to reference. %s",
                    type(exc).__name__,
                    exc,
                )
        return self._fallback.decide(request)

    def _derive_seed(self, context: Mapping[str, Any] | None) -> str:
        """Derive a 16-hex-char (64-bit) seed from context, a nonce and time."""
        nonce = next(self._counter)
        material = f"{nonce}:{sorted((context or {}).items())}:{time.time_ns()}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]