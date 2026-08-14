"""Reference decision engine (in-process).

The reference implementation is the availability fallback of the decision
fabric: when no JVM decision engine is present (jar not built, no Java runtime,
subprocess failure), decisions are rendered here with Python's :mod:`random`
module using the same uniform distribution a healthy engine would produce. This
keeps the application layer available without any toolchain dependency.
"""
from __future__ import annotations

import hashlib
import random
from typing import Any

from boombot.casino.decisionengine.domain.decision import Decision, DecisionKind, DecisionRequest
from boombot.casino.decisionengine.infrastructure.decision_engine_port import IDecisionEngine

#: Number of symbols in the Zeus reel vocabulary (see ``zeus.domain.reel``).
_ZEUS_SYMBOL_COUNT = 9

_FACE_POCKETS: Any = [0, "00", *range(1, 37)]


class ReferenceDecisionEngine(IDecisionEngine):
    """An in-process, always-available decision provider."""

    def is_available(self) -> bool:
        return True

    def decide(self, request: DecisionRequest) -> Decision:
        kind = request.get_kind()
        if kind is DecisionKind.ROULETTE_SPIN:
            payload: dict[str, Any] = {"kind": kind.value, "pocket": random.choice(_FACE_POCKETS)}
            payload["label"] = str(payload["pocket"])
        elif kind is DecisionKind.CRAPS_ROLL:
            die1 = random.randint(1, 6)
            die2 = random.randint(1, 6)
            payload = {"kind": kind.value, "die1": die1, "die2": die2, "sum": die1 + die2}
        elif kind is DecisionKind.ZEUS_SPIN:
            payload = {
                "kind": kind.value,
                "rows": 5,
                "cols": 5,
                "symbols": [random.randint(0, _ZEUS_SYMBOL_COUNT - 1) for _ in range(25)],
            }
        elif kind is DecisionKind.FAIRNESS_HASH:
            payload = {
                "kind": kind.value,
                "hash": hashlib.sha256(request.get_seed().encode("utf-8")).hexdigest()[:16],
            }
        else:
            raise ValueError(f"Unsupported decision kind: {kind}")

        return Decision(
            kind=kind,
            payload=payload,
            engine="reference",
            atomic="python",
            seed=request.get_seed(),
            request_id=request.get_request_id(),
        )