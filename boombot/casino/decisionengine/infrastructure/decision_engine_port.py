"""Decision-engine port.

The :class:`IDecisionEngine` contract is the seam between the application
service and whatever renders decisions. Both the JVM gateway and the in-process
reference implementation implement it, keeping the application layer
independent of which provider is running.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from boombot.casino.decisionengine.domain.decision import Decision, DecisionRequest


class IDecisionEngine(ABC):
    """Port describing a decision provider."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether this provider can currently render decisions."""
        raise NotImplementedError

    @abstractmethod
    def decide(self, request: DecisionRequest) -> Decision:
        """Render a single decision for ``request``.

        Providers may raise ``DecisionEngineUnavailableException`` or
        ``DecisionEngineFailureException`` to signal the caller to degrade.
        """
        raise NotImplementedError