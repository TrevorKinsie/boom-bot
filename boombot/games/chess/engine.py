"""Persistent Stockfish UCI process wrapper."""

from __future__ import annotations

import logging
import queue
import re
import subprocess
import threading
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

    def _ensure_started(self) -> None:
        if self._process and self._process.poll() is None:
            return

        logger.info("Starting Stockfish from %s", self.engine_path)
        self._process = subprocess.Popen(
            [self.engine_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self._output = queue.Queue()
        self._reader = threading.Thread(target=self._read_output, daemon=True)
        self._reader.start()

        self._send("uci")
        self._wait_for(lambda line: line == "uciok")
        self._send(f"setoption name Hash value {self.hash_mb}")
        self._send(f"setoption name Threads value {self.threads}")
        self._send(f"setoption name Skill Level value {self._skill_level}")
        self._send("isready")
        self._wait_for(lambda line: line == "readyok")
        logger.info("Stockfish is ready")

    def _read_output(self) -> None:
        assert self._process is not None
        assert self._process.stdout is not None
        try:
            for line in self._process.stdout:
                self._output.put(line.strip())
        finally:
            self._output.put(None)

    def _send(self, command: str) -> None:
        if not self._process or not self._process.stdin:
            raise RuntimeError("Stockfish is not running")
        self._process.stdin.write(command + "\n")
        self._process.stdin.flush()

    def _wait_for(self, predicate, timeout: float | None = None) -> list[str]:
        lines: list[str] = []
        deadline = timeout or self.timeout
        while True:
            try:
                line = self._output.get(timeout=deadline)
            except queue.Empty as exc:
                raise TimeoutError("Timed out waiting for Stockfish") from exc
            if line is None:
                raise RuntimeError("Stockfish exited unexpectedly")
            lines.append(line)
            if predicate(line):
                return lines

    def _set_skill_level(self, skill_level: int) -> None:
        clamped = max(0, min(20, int(skill_level)))
        if clamped == self._skill_level:
            return
        self._send(f"setoption name Skill Level value {clamped}")
        self._send("isready")
        self._wait_for(lambda line: line == "readyok")
        self._skill_level = clamped

    def get_best_move(
        self,
        fen: str,
        depth: int | None = None,
        skill_level: int = 20,
    ) -> str:
        with self._lock:
            self._ensure_started()
            self._set_skill_level(skill_level)
            self._send(f"position fen {fen}")
            self._send(f"go depth {depth or self.default_depth}")
            lines = self._wait_for(lambda line: line.startswith("bestmove"))
            best_move = lines[-1].split()[1] if len(lines[-1].split()) > 1 else ""
            if not best_move or best_move == "(none)":
                raise RuntimeError("Stockfish returned no legal move")
            return best_move

    def get_evaluation(
        self,
        fen: str,
        depth: int | None = None,
        skill_level: int = 20,
    ) -> dict[str, int | str]:
        with self._lock:
            self._ensure_started()
            self._set_skill_level(skill_level)
            self._send(f"position fen {fen}")
            self._send(f"go depth {depth or self.default_depth}")
            lines = self._wait_for(lambda line: line.startswith("bestmove"))

            score = 0
            for line in lines:
                match = re.search(r"\bscore\s+(cp|mate)\s+(-?\d+)", line)
                if not match:
                    continue
                value = int(match.group(2))
                score = value if match.group(1) == "cp" else (
                    10000 - value if value > 0 else -10000 - value
                )

            best_move = lines[-1].split()[1] if len(lines[-1].split()) > 1 else ""
            return {"score": score, "best_move": best_move}

    def quit(self) -> None:
        with self._lock:
            if not self._process:
                return
            try:
                if self._process.poll() is None:
                    self._send("quit")
                    self._process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                self._process.kill()
            finally:
                self._process = None
