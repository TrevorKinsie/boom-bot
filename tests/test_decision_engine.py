"""
Decision Engine Tests.

Validates the decision fabric: the domain model, the output specifications,
the reference (in-process) implementation, the DecisionService degradation
semantics, and the JVM gateway's JSON-lines protocol against a stubbed
subprocess so no real Java/Rust runtime is required in CI.
"""

import json
from unittest import mock

import pytest

from boombot.casino.decisionengine.application.decision_service import DecisionService
from boombot.casino.decisionengine.domain.decision import Decision, DecisionKind, DecisionRequest
from boombot.casino.decisionengine.domain.decision_specifications import (
    CrapsRollSpecification,
    RoulettePocketSpecification,
    ZeusGridSpecification,
    validate_decision,
)
from boombot.casino.decisionengine.domain.exceptions import (
    DecisionEngineFailureException,
    DecisionEngineUnavailableException,
)
from boombot.casino.decisionengine.infrastructure.decision_engine_port import IDecisionEngine
from boombot.casino.decisionengine.infrastructure.jvm_decision_engine_gateway import (
    JvmDecisionEngineGateway,
)
from boombot.casino.decisionengine.infrastructure.reference_decision_engine import (
    ReferenceDecisionEngine,
)


def make_decision(kind, **payload):
    payload.setdefault("kind", kind.value)
    return Decision(kind=kind, payload=payload)


class TestDecisionModel:
    def test_request_to_wire(self):
        request = DecisionRequest(
            DecisionKind.ROULETTE_SPIN,
            "1a2b3c",
            context={"tenant": "ch1"},
            request_id="r1",
        )
        wire = request.to_wire()
        assert wire["kind"] == "ROULETTE_SPIN"
        assert wire["seed"] == "1a2b3c"
        assert wire["id"] == "r1"
        assert wire["context"] == {"tenant": "ch1"}

    def test_decision_from_response(self):
        response = {
            "id": "r1",
            "engine": "jvm",
            "atomic": "rust",
            "latencyMs": 3,
            "seed": "cafe",
            "decision": {"kind": "ROULETTE_SPIN", "pocket": 17, "label": "17"},
        }
        decision = Decision.from_response(response)
        assert decision.get_kind() is DecisionKind.ROULETTE_SPIN
        assert decision.get_engine() == "jvm"
        assert decision.get_atomic_provider() == "rust"
        assert decision.get("pocket") == 17
        assert decision.get_seed() == "cafe"
        assert decision.get_request_id() == "r1"

    def test_decision_from_response_missing_payload(self):
        with pytest.raises(ValueError):
            Decision.from_response({"engine": "jvm"})


class TestSpecifications:
    def test_valid_roulette_passes(self):
        spec = RoulettePocketSpecification()
        assert spec.is_satisfied_by(make_decision(DecisionKind.ROULETTE_SPIN, pocket=36))
        assert spec.is_satisfied_by(make_decision(DecisionKind.ROULETTE_SPIN, pocket="00"))
        assert spec.is_satisfied_by(make_decision(DecisionKind.ROULETTE_SPIN, pocket=0))

    def test_invalid_roulette_fails(self):
        spec = RoulettePocketSpecification()
        assert not spec.is_satisfied_by(make_decision(DecisionKind.ROULETTE_SPIN, pocket=37))
        assert not spec.is_satisfied_by(make_decision(DecisionKind.ROULETTE_SPIN, pocket=-1))
        assert not spec.is_satisfied_by(make_decision(DecisionKind.CRAPS_ROLL, pocket=3))

    def test_valid_craps_passes(self):
        spec = CrapsRollSpecification()
        decision = make_decision(DecisionKind.CRAPS_ROLL, die1=2, die2=3, sum=5)
        assert spec.is_satisfied_by(decision)

    def test_invalid_craps_sum_fails(self):
        spec = CrapsRollSpecification()
        decision = make_decision(DecisionKind.CRAPS_ROLL, die1=2, die2=3, sum=99)
        assert not spec.is_satisfied_by(decision)

    def test_valid_zeus_passes(self):
        spec = ZeusGridSpecification()
        symbols = [i % 9 for i in range(25)]
        decision = make_decision(DecisionKind.ZEUS_SPIN, rows=5, cols=5, symbols=symbols)
        assert spec.is_satisfied_by(decision)

    def test_invalid_zeus_length_fails(self):
        spec = ZeusGridSpecification()
        decision = make_decision(DecisionKind.ZEUS_SPIN, rows=5, cols=5, symbols=[0, 1, 2])
        assert not spec.is_satisfied_by(decision)

    def test_validate_decision_raises_on_invalid(self):
        bad = make_decision(DecisionKind.CRAPS_ROLL, die1=7, die2=2, sum=9)
        with pytest.raises(ValueError):
            validate_decision(bad)

class TestReferenceEngine:
    @pytest.mark.parametrize(
        "kind",
        [DecisionKind.ROULETTE_SPIN, DecisionKind.CRAPS_ROLL, DecisionKind.ZEUS_SPIN],
    )
    def test_reference_renders_valid_decision(self, kind):
        engine = ReferenceDecisionEngine()
        request = DecisionRequest(kind, "cafe")
        decision = engine.decide(request)
        assert decision.get_kind() is kind
        assert decision.get_engine() == "reference"
        validate_decision(decision)

    def test_reference_fairness_hash(self):
        engine = ReferenceDecisionEngine()
        decision = engine.decide(DecisionRequest(DecisionKind.FAIRNESS_HASH, "cafe"))
        assert len(decision.get("hash")) == 16


class TestDecisionService:
    class _FlakyPrimary(IDecisionEngine):
        def __init__(self, available=True):
            self._available = available

        def is_available(self):
            return self._available

        def decide(self, request):
            raise DecisionEngineUnavailableException("primary down")

    def test_uses_primary_when_available(self):
        primary = mock.Mock(spec=IDecisionEngine)
        primary.is_available.return_value = True
        primary.decide.return_value = make_decision(DecisionKind.ROULETTE_SPIN, pocket=5)
        service = DecisionService(primary, fallback=ReferenceDecisionEngine())
        decision = service.decide(DecisionKind.ROULETTE_SPIN, context={"tenant": "ch1"})
        assert decision.get("pocket") == 5
        primary.decide.assert_called_once()

    def test_falls_back_when_primary_unavailable(self):
        primary = TestDecisionService._FlakyPrimary(available=False)
        service = DecisionService(primary, fallback=ReferenceDecisionEngine())
        decision = service.decide(DecisionKind.CRAPS_ROLL)
        assert decision.get_engine() == "reference"

    def test_falls_back_when_primary_fails(self):
        primary = TestDecisionService._FlakyPrimary(available=True)
        service = DecisionService(primary, fallback=ReferenceDecisionEngine())
        decision = service.decide(DecisionKind.ZEUS_SPIN)
        assert decision.get_engine() == "reference"

    def test_fairness_hash(self):
        primary = mock.Mock(spec=IDecisionEngine)
        primary.is_available.return_value = True
        primary.decide.return_value = make_decision(DecisionKind.FAIRNESS_HASH, hash="abc123")
        service = DecisionService(primary, fallback=ReferenceDecisionEngine())
        assert service.fairness_hash() == "abc123"
class _FakeStdin:
    def __init__(self):
        self.written = []

    def write(self, text):
        self.written.append(text)

    def flush(self):
        pass

    def close(self):
        pass


class _FakeStdout:
    def __init__(self, lines):
        self._lines = list(lines)

    def readline(self):
        return self._lines.pop(0) if self._lines else ""


class _FakeProc:
    def __init__(self, lines):
        self.stdin = _FakeStdin()
        self.stdout = _FakeStdout(lines)
        self.terminated = False

    def poll(self):
        return None

    def terminate(self):
        self.terminated = True


class TestJvmGateway:
    def test_not_available_without_jar(self):
        gateway = JvmDecisionEngineGateway("/no/such/jar.jar", java_command="java")
        assert gateway.is_available() is False

    def test_decide_round_trips_protocol(self, tmp_path):
        jar = tmp_path / "engine.jar"
        jar.write_text("not a real jar")
        response = {
            "id": "r1",
            "engine": "jvm",
            "atomic": "java",
            "latencyMs": 1,
            "seed": "cafe",
            "decision": {"kind": "ROULETTE_SPIN", "pocket": 7, "label": "7"},
        }
        fake_proc = _FakeProc([json.dumps(response)])

        gateway = JvmDecisionEngineGateway(str(jar), rust_bin=None, java_command="java")
        with mock.patch(
            "boombot.casino.decisionengine.infrastructure.jvm_decision_engine_gateway.subprocess.Popen",
            return_value=fake_proc,
        ):
            decision = gateway.decide(
                DecisionRequest(DecisionKind.ROULETTE_SPIN, "cafe", request_id="r1")
            )

        assert decision.get_kind() is DecisionKind.ROULETTE_SPIN
        assert decision.get("pocket") == 7
        assert decision.get_engine() == "jvm"
        written = "".join(fake_proc.stdin.written)
        assert '"kind": "ROULETTE_SPIN"' in written
        assert '"seed": "cafe"' in written
        gateway.close()

    def test_engine_error_surfaces_as_failure(self, tmp_path):
        jar = tmp_path / "engine.jar"
        jar.write_text("x")
        fake_proc = _FakeProc([json.dumps({"error": "boom"})])
        gateway = JvmDecisionEngineGateway(str(jar))
        with mock.patch(
            "boombot.casino.decisionengine.infrastructure.jvm_decision_engine_gateway.subprocess.Popen",
            return_value=fake_proc,
        ):
            with pytest.raises(DecisionEngineFailureException):
                gateway.decide(
                    DecisionRequest(DecisionKind.CRAPS_ROLL, "cafe", request_id="r1")
                )
        gateway.close()

    def test_empty_response_is_unavailable(self, tmp_path):
        jar = tmp_path / "engine.jar"
        jar.write_text("x")
        fake_proc = _FakeProc([])
        gateway = JvmDecisionEngineGateway(str(jar))
        with mock.patch(
            "boombot.casino.decisionengine.infrastructure.jvm_decision_engine_gateway.subprocess.Popen",
            return_value=fake_proc,
        ):
            with pytest.raises(DecisionEngineUnavailableException):
                gateway.decide(
                    DecisionRequest(DecisionKind.ROULETTE_SPIN, "cafe", request_id="r1")
                )
        gateway.close()