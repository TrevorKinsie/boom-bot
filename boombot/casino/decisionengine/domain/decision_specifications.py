"""Decision output specifications.

Discrete, composable predicates over a rendered :class:`Decision` payload.
Each specification pins the invariant of a single game family so the surface
area of a misbehaving engine (or a mis-wired reference implementation) is
caught at the boundary rather than silently corrupting the wallet.
"""
from __future__ import annotations

from typing import Any, Sequence

from boombot.casino.decisionengine.domain.decision import Decision, DecisionKind


class DecisionSpecification:
    """Base interface for predicates over a decision payload."""

    def is_satisfied_by(self, decision: Decision) -> bool:
        raise NotImplementedError


class RoulettePocketSpecification(DecisionSpecification):
    """The pocket must be an integer in ``0..=36`` or the string ``"00"``."""

    _VALID = frozenset([0, "00", *(range(1, 37))])

    def is_satisfied_by(self, decision: Decision) -> bool:
        if decision.get_kind() is not DecisionKind.ROULETTE_SPIN:
            return False
        pocket = decision.get("pocket")
        if isinstance(pocket, int):
            return pocket in self._VALID
        return pocket == "00"


class CrapsRollSpecification(DecisionSpecification):
    """Both die faces must be integers in ``1..=6`` and sum to the payload sum."""

    def is_satisfied_by(self, decision: Decision) -> bool:
        if decision.get_kind() is not DecisionKind.CRAPS_ROLL:
            return False
        die1 = decision.get("die1")
        die2 = decision.get("die2")
        total = decision.get("sum")
        faces = (die1, die2)
        if not all(isinstance(face, int) for face in faces):
            return False
        return (
            1 <= die1 <= 6
            and 1 <= die2 <= 6
            and isinstance(total, int)
            and total == die1 + die2
        )


class ZeusGridSpecification(DecisionSpecification):
    """The symbol vector must be ``rows * cols`` long with each index in ``0..=8``."""

    def is_satisfied_by(self, decision: Decision) -> bool:
        if decision.get_kind() is not DecisionKind.ZEUS_SPIN:
            return False
        symbols = decision.get("symbols")
        rows = decision.get("rows", 5)
        cols = decision.get("cols", 5)
        if not isinstance(symbols, Sequence) or isinstance(symbols, (str, bytes)):
            return False
        expected = int(rows) * int(cols)
        return len(symbols) == expected and all(
            isinstance(sym, int) and 0 <= sym <= 8 for sym in symbols
        )


#: Map of decision kind to the specification guarding its output invariant.
SPECIFICATION_BY_KIND: dict[DecisionKind, DecisionSpecification] = {
    DecisionKind.ROULETTE_SPIN: RoulettePocketSpecification(),
    DecisionKind.CRAPS_ROLL: CrapsRollSpecification(),
    DecisionKind.ZEUS_SPIN: ZeusGridSpecification(),
}


def validate_decision(decision: Decision) -> None:
    """Raise :class:`ValueError` if ``decision`` violates its family invariant.

    Fairness hashes carry no positional invariant and are never validated.
    """
    spec = SPECIFICATION_BY_KIND.get(decision.get_kind())
    if spec is None:
        return
    if not spec.is_satisfied_by(decision):
        raise ValueError(f"Decision fails its output specification: {decision!r}")