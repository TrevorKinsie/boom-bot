"""Decision value objects.

The decision fabric speaks in small, immutable values:

* :class:`DecisionKind` enumerates the decisions the fabric can render.
* :class:`DecisionRequest` is what the orchestrator hands the engine.
* :class:`Decision` is what the engine hands back.

The wire format is line-delimited JSON shared with the JVM middleware; the
:class:`DecisionRequest.to_wire` and :class:`Decision.from_response` pair are the
single place those bytes are (de)serialised.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Mapping


class DecisionKind(Enum):
    """The canonical decisions the fabric can render.

    Member *values* equal the wire identifiers used by the Java middleware and
    the Rust atomic-logic layer.
    """

    ROULETTE_SPIN = "ROULETTE_SPIN"
    CRAPS_ROLL = "CRAPS_ROLL"
    ZEUS_SPIN = "ZEUS_SPIN"
    FAIRNESS_HASH = "FAIRNESS_HASH"

    @classmethod
    def from_wire(cls, raw: str) -> "DecisionKind":
        """Resolve a wire identifier back to its enum member."""
        try:
            return cls[raw]
        except KeyError:
            raise ValueError(f"Unknown decision kind: {raw!r}")


class DecisionRequest:
    """An immutable request for a single decision."""

    __slots__ = ("_request_id", "_kind", "_seed", "_context")

    def __init__(
        self,
        kind: DecisionKind,
        seed: str,
        context: Mapping[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        self._kind = kind
        self._seed = seed
        self._context = dict(context) if context else {}
        self._request_id = request_id or f"{kind.name.lower()}-{seed}"

    def get_kind(self) -> DecisionKind:
        return self._kind

    def get_seed(self) -> str:
        return self._seed

    def get_context(self) -> dict[str, Any]:
        return dict(self._context)

    def get_request_id(self) -> str:
        return self._request_id

    def to_wire(self) -> dict[str, Any]:
        """Serialize to the JSON wire map consumed by the JVM engine."""
        wire: dict[str, Any] = {
            "id": self._request_id,
            "kind": self._kind.value,
            "seed": self._seed,
        }
        if self._context:
            wire["context"] = self._context
        return wire

    def __repr__(self) -> str:
        return (
            f"DecisionRequest(request_id={self._request_id!r}, "
            f"kind={self._kind.name}, seed={self._seed!r})"
        )


class Decision:
    """An immutable rendered decision returned by an engine provider."""

    __slots__ = (
        "_kind",
        "_payload",
        "_engine",
        "_atomic",
        "_latency_ms",
        "_seed",
        "_request_id",
    )

    def __init__(
        self,
        kind: DecisionKind,
        payload: Mapping[str, Any],
        engine: str = "reference",
        atomic: str = "python",
        latency_ms: int = 0,
        seed: str = "",
        request_id: str | None = None,
    ) -> None:
        self._kind = kind
        self._payload = dict(payload)
        self._engine = engine
        self._atomic = atomic
        self._latency_ms = int(latency_ms)
        self._seed = seed
        self._request_id = request_id

    def get_kind(self) -> DecisionKind:
        return self._kind

    def get_payload(self) -> dict[str, Any]:
        return dict(self._payload)

    def get(self, key: str, default: Any = None) -> Any:
        """Read a field from the decision payload."""
        return self._payload.get(key, default)

    def get_engine(self) -> str:
        return self._engine

    def get_atomic_provider(self) -> str:
        return self._atomic

    def get_latency_ms(self) -> int:
        return self._latency_ms

    def get_seed(self) -> str:
        return self._seed

    def get_request_id(self) -> str | None:
        return self._request_id

    @classmethod
    def from_response(cls, response: Mapping[str, Any]) -> "Decision":
        """Rebuild a :class:`Decision` from a JVM engine response map."""
        decision_map = response.get("decision")
        if not isinstance(decision_map, Mapping):
            raise ValueError("Decision response is missing its 'decision' payload")
        kind = DecisionKind.from_wire(str(decision_map.get("kind")))
        return cls(
            kind=kind,
            payload=decision_map,
            engine=str(response.get("engine", "jvm")),
            atomic=str(response.get("atomic", "java")),
            latency_ms=int(response.get("latencyMs", 0) or 0),
            seed=str(response.get("seed", "")),
            request_id=response.get("id"),
        )

    def __repr__(self) -> str:
        return (
            f"Decision(kind={self._kind.name}, engine={self._engine!r}, "
            f"atomic={self._atomic!r}, payload={self._payload!r})"
        )