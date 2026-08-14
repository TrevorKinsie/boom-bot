"""JVM decision-engine gateway.

The production adapter of the decision fabric. It hosts the JVM decision
engine (``decision-engine/build/jvm-decision-engine.jar``) as a long-lived
JSON-lines subprocess -- one request line on stdin per decision, one response
line on stdout -- and translates the engine's response into a domain
:class:`Decision`.

The process is started lazily and kept warm across decisions; a wedged or
crashed child is torn down and restarted on the next call, and the machine
falls back to the reference implementation if the jar or Java runtime is
missing.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any

from boombot.casino.decisionengine.domain.decision import Decision, DecisionRequest
from boombot.casino.decisionengine.domain.exceptions import (
    DecisionEngineFailureException,
    DecisionEngineUnavailableException,
)
from boombot.casino.decisionengine.infrastructure.decision_engine_port import IDecisionEngine

logger = logging.getLogger(__name__)


class JvmDecisionEngineGateway(IDecisionEngine):
    """Hosts the JVM decision engine as a persistent subprocess."""

    def __init__(
        self,
        jar_path: str,
        rust_bin: str | None = None,
        timeout_seconds: float = 5.0,
        java_command: str = "java",
    ) -> None:
        self._jar = str(jar_path)
        self._rust_bin = rust_bin
        self._timeout_seconds = float(timeout_seconds)
        self._java_command = java_command
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    # --- IEngine lifecycle ---
    def is_available(self) -> bool:
        if not Path(self._jar).is_file():
            return False
        return shutil.which(self._java_command) is not None

    def decide(self, request: DecisionRequest) -> Decision:
        if not self.is_available():
            raise DecisionEngineUnavailableException(
                f"JVM decision engine not available (jar={self._jar!r})"
            )
        request_line = json.dumps(request.to_wire())
        response = self._round_trip(request_line, request.get_request_id())
        if "error" in response:
            raise DecisionEngineFailureException(str(response.get("error")))
        if not isinstance(response.get("decision"), dict):
            raise DecisionEngineFailureException(
                "JVM decision engine returned a response without a decision payload"
            )
        return Decision.from_response(response)

    def close(self) -> None:
        """Terminate the hosted child process, if any."""
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        try:
            proc.stdin.close()  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001 - best effort teardown
            pass
        try:
            proc.terminate()
        except Exception:  # noqa: BLE001
            pass

    # --- Subprocess plumbing ---
    def _round_trip(self, request_line: str, request_id: str) -> dict[str, Any]:
        with self._lock:
            proc = self._ensure_process()
            try:
                assert proc.stdin is not None and proc.stdout is not None
                proc.stdin.write(request_line + "\n")
                proc.stdin.flush()
                response_line = proc.stdout.readline()
            except (OSError, ValueError) as exc:
                self.close()
                raise DecisionEngineUnavailableException(
                    f"JVM decision engine subprocess failed: {exc}"
                ) from exc

            if not response_line:
                self.close()
                raise DecisionEngineUnavailableException(
                    "JVM decision engine closed without a response"
                )
            try:
                response = json.loads(response_line)
            except ValueError as exc:
                self.close()
                raise DecisionEngineFailureException(
                    f"JVM decision engine returned malformed JSON: {response_line!r}"
                ) from exc

            if response.get("id") not in (None, request_id):
                raise DecisionEngineFailureException(
                    f"JVM decision engine response id mismatch: {response.get('id')!r}"
                )
            return response

    def _ensure_process(self) -> subprocess.Popen:
        proc = self._proc
        if proc is not None and proc.poll() is None:
            return proc

        env = os.environ.copy()
        if self._rust_bin:
            env["DECISION_ENGINE_RUST_BIN"] = self._rust_bin
        env.setdefault("DECISION_ENGINE_TIMEOUT_SECONDS", str(self._timeout_seconds))

        logger.debug("Starting JVM decision engine subprocess: java -jar %s", self._jar)
        self._proc = subprocess.Popen(
            [self._java_command, "-jar", self._jar],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=env,
        )
        return self._proc