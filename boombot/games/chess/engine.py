"""Persistent Stockfish UCI process wrapper."""

from __future__ import annotations

from collections import deque
import logging
import queue
import re
import subprocess
import threading
import time
from pathlib import Path

from boombot.core.config import (
    STOCKFISH_DEPTH,
    STOCKFISH_HASH_MB,
    STOCKFISH_PATH,
    STOCKFISH_THREADS,
)

logger = logging.getLogger(__name__)


class StockfishEngine:
    """Serialize Stockfish requests and expose best-move/evaluation calls."""

    def __init__(
        self,
        engine_path: str | Path = STOCKFISH_PATH,
        *,
        hash_mb: int = STOCKFISH_HASH_MB,
        threads: int = STOCKFISH_THREADS,
        default_depth: int = STOCKFISH_DEPTH,
        timeout: float = 120.0,
    ):
        self.engine_path = str(engine_path)
        self.hash_mb = max(1, hash_mb)
        self.threads = max(1, threads)
        self.default_depth = max(1, default_depth)
        self.timeout = timeout
        self._process: subprocess.Popen[str] | None = None
        self._output: queue.Queue[str | None] = queue.Queue()
        self._reader: threading.Thread | None = None
        self._lock = threading.RLock()
        self._skill_level = 20
        self._last_command: str | None = None
        self._output_tail: deque[str] = deque(maxlen=80)

    def _ensure_started(self) -> None:
        if self._process and self._process.poll() is None:
            logger.debug(
                "Stockfish process already running pid=%s",
                self._process.pid,
            )
            return

        logger.info(
            "Starting Stockfish path=%s hash_mb=%s threads=%s default_depth=%s "
            "timeout_seconds=%s",
            self.engine_path,
            self.hash_mb,
            self.threads,
            self.default_depth,
            self.timeout,
        )
        self._output_tail.clear()
        try:
            self._process = subprocess.Popen(
                [self.engine_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            logger.info("Stockfish process spawned pid=%s", self._process.pid)
            self._output = queue.Queue()
            self._reader = threading.Thread(target=self._read_output, daemon=True)
            self._reader.start()

            self._send("uci")
            self._wait_for(lambda line: line == "uciok", operation="uci_handshake")
            self._send(f"setoption name Hash value {self.hash_mb}")
            self._send(f"setoption name Threads value {self.threads}")
            self._send(f"setoption name Skill Level value {self._skill_level}")
            self._send("isready")
            self._wait_for(lambda line: line == "readyok", operation="ready_handshake")
            logger.info("Stockfish is ready pid=%s", self._process.pid)
        except Exception:
            logger.exception(
                "Stockfish startup failed path=%s pid=%s last_command=%r "
                "output_tail=%r",
                self.engine_path,
                self._process.pid if self._process else None,
                self._last_command,
                list(self._output_tail),
            )
            process = self._process
            self._process = None
            if process and process.poll() is None:
                try:
                    process.kill()
                    process.wait(timeout=5)
                except Exception:
                    logger.exception("Failed to clean up Stockfish after startup failure pid=%s", process.pid)
            raise

    def _read_output(self) -> None:
        process = self._process
        assert process is not None
        assert process.stdout is not None
        pid = process.pid
        try:
            for line in process.stdout:
                normalized = line.strip()
                self._output_tail.append(normalized)
                self._output.put(normalized)
                logger.debug("Stockfish output pid=%s line=%r", pid, normalized)
        except Exception:
            logger.exception("Stockfish output reader failed pid=%s", pid)
        finally:
            self._output.put(None)
            logger.warning("Stockfish output stream closed pid=%s", pid)

    def _send(self, command: str) -> None:
        if not self._process or not self._process.stdin:
            logger.error(
                "Cannot send Stockfish command because process is unavailable "
                "command=%r",
                command,
            )
            raise RuntimeError("Stockfish is not running")
        self._last_command = command
        logger.debug("Sending Stockfish command pid=%s command=%r", self._process.pid, command)
        try:
            self._process.stdin.write(command + "\n")
            self._process.stdin.flush()
        except Exception:
            logger.exception(
                "Stockfish command write failed pid=%s command=%r poll=%s",
                self._process.pid,
                command,
                self._process.poll(),
            )
            raise

    def _wait_for(
        self,
        predicate,
        timeout: float | None = None,
        *,
        operation: str = "unknown",
    ) -> list[str]:
        lines: list[str] = []
        timeout_seconds = timeout if timeout is not None else self.timeout
        deadline = time.monotonic() + timeout_seconds
        logger.debug(
            "Waiting for Stockfish response operation=%s timeout_seconds=%s "
            "last_command=%r",
            operation,
            timeout_seconds,
            self._last_command,
        )
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                logger.error(
                    "Stockfish response timed out operation=%s timeout_seconds=%s "
                    "lines_received=%s last_command=%r output_tail=%r pid=%s",
                    operation,
                    timeout_seconds,
                    len(lines),
                    self._last_command,
                    list(self._output_tail),
                    self._process.pid if self._process else None,
                )
                raise TimeoutError(
                    f"Timed out waiting for Stockfish during {operation}"
                )
            try:
                line = self._output.get(timeout=remaining)
            except queue.Empty as exc:
                logger.error(
                    "Stockfish response queue timed out operation=%s "
                    "timeout_seconds=%s lines_received=%s last_command=%r "
                    "output_tail=%r pid=%s",
                    operation,
                    timeout_seconds,
                    len(lines),
                    self._last_command,
                    list(self._output_tail),
                    self._process.pid if self._process else None,
                )
                raise TimeoutError(
                    f"Timed out waiting for Stockfish during {operation}"
                ) from exc
            if line is None:
                process = self._process
                return_code = process.poll() if process else None
                logger.error(
                    "Stockfish exited while waiting operation=%s lines_received=%s "
                    "last_command=%r output_tail=%r pid=%s return_code=%s",
                    operation,
                    len(lines),
                    self._last_command,
                    list(self._output_tail),
                    process.pid if process else None,
                    return_code,
                )
                raise RuntimeError(
                    f"Stockfish exited unexpectedly during {operation} "
                    f"(return_code={return_code})"
                )
            lines.append(line)
            if predicate(line):
                logger.debug(
                    "Stockfish response matched operation=%s lines_received=%s",
                    operation,
                    len(lines),
                )
                return lines

    def _set_skill_level(self, skill_level: int) -> None:
        clamped = max(0, min(20, int(skill_level)))
        if clamped == self._skill_level:
            logger.debug("Stockfish skill level unchanged skill_level=%s", clamped)
            return
        logger.info(
            "Changing Stockfish skill level from=%s to=%s",
            self._skill_level,
            clamped,
        )
        self._send(f"setoption name Skill Level value {clamped}")
        self._send("isready")
        self._wait_for(lambda line: line == "readyok", operation="skill_level_handshake")
        self._skill_level = clamped

    def get_best_move(
        self,
        fen: str,
        depth: int | None = None,
        skill_level: int = 20,
    ) -> str:
        requested_depth = depth or self.default_depth
        started = time.monotonic()
        logger.info(
            "Stockfish best-move request started fen=%r depth=%s skill_level=%s",
            fen,
            requested_depth,
            skill_level,
        )
        with self._lock:
            try:
                self._ensure_started()
                self._set_skill_level(skill_level)
                self._send(f"position fen {fen}")
                self._send(f"go depth {requested_depth}")
                lines = self._wait_for(
                    lambda line: line.startswith("bestmove"),
                    operation="best_move",
                )
                parts = lines[-1].split()
                best_move = parts[1] if len(parts) > 1 else ""
                if not best_move or best_move == "(none)":
                    logger.error(
                        "Stockfish returned no legal move fen=%r depth=%s "
                        "skill_level=%s response=%r",
                        fen,
                        requested_depth,
                        skill_level,
                        lines[-1] if lines else None,
                    )
                    raise RuntimeError("Stockfish returned no legal move")
                logger.info(
                    "Stockfish best-move request completed best_move=%s duration_ms=%.1f",
                    best_move,
                    (time.monotonic() - started) * 1000,
                )
                return best_move
            except Exception as exc:
                logger.exception(
                    "Stockfish best-move request failed fen=%r depth=%s "
                    "skill_level=%s error_type=%s last_command=%r output_tail=%r",
                    fen,
                    requested_depth,
                    skill_level,
                    type(exc).__name__,
                    self._last_command,
                    list(self._output_tail),
                )
                raise

    def get_evaluation(
        self,
        fen: str,
        depth: int | None = None,
        skill_level: int = 20,
    ) -> dict[str, int | str]:
        requested_depth = depth or self.default_depth
        started = time.monotonic()
        logger.info(
            "Stockfish evaluation request started fen=%r depth=%s skill_level=%s",
            fen,
            requested_depth,
            skill_level,
        )
        with self._lock:
            try:
                self._ensure_started()
                self._set_skill_level(skill_level)
                self._send(f"position fen {fen}")
                self._send(f"go depth {requested_depth}")
                lines = self._wait_for(
                    lambda line: line.startswith("bestmove"),
                    operation="evaluation",
                )

                score = 0
                score_lines = 0
                for line in lines:
                    match = re.search(r"\bscore\s+(cp|mate)\s+(-?\d+)", line)
                    if not match:
                        continue
                    score_lines += 1
                    value = int(match.group(2))
                    score = value if match.group(1) == "cp" else (
                        10000 - value if value > 0 else -10000 - value
                    )

                parts = lines[-1].split()
                best_move = parts[1] if len(parts) > 1 else ""
                logger.info(
                    "Stockfish evaluation request completed score=%s best_move=%r "
                    "score_lines=%s duration_ms=%.1f",
                    score,
                    best_move,
                    score_lines,
                    (time.monotonic() - started) * 1000,
                )
                return {"score": score, "best_move": best_move}
            except Exception as exc:
                logger.exception(
                    "Stockfish evaluation request failed fen=%r depth=%s "
                    "skill_level=%s error_type=%s last_command=%r output_tail=%r",
                    fen,
                    requested_depth,
                    skill_level,
                    type(exc).__name__,
                    self._last_command,
                    list(self._output_tail),
                )
                raise

    def quit(self) -> None:
        with self._lock:
            if not self._process:
                logger.debug("Stockfish quit requested but process is already stopped")
                return
            process = self._process
            logger.info("Stopping Stockfish pid=%s", process.pid)
            try:
                if process.poll() is None:
                    self._send("quit")
                    process.wait(timeout=5)
                logger.info("Stockfish stopped pid=%s return_code=%s", process.pid, process.returncode)
            except (OSError, subprocess.TimeoutExpired):
                logger.exception("Stockfish graceful shutdown failed pid=%s; killing process", process.pid)
                try:
                    process.kill()
                    process.wait(timeout=5)
                except Exception:
                    logger.exception("Stockfish forced shutdown failed pid=%s", process.pid)
            finally:
                self._process = None
