import os
import shutil
import subprocess
from pathlib import Path

import chess
import pytest

from boombot.core.config import STOCKFISH_PATH
from boombot.games.chess.engine import StockfishEngine


def _resolve_stockfish_path() -> Path | None:
    configured_path = Path(STOCKFISH_PATH)
    if configured_path.is_absolute():
        return configured_path if configured_path.is_file() else None

    resolved_path = shutil.which(STOCKFISH_PATH)
    return Path(resolved_path) if resolved_path else None


# Stockfish is only guaranteed to be present in CI/staging (see
# .github/workflows/test.yml which installs it via apt). Skip the tests in any
# environment where the binary can't be resolved so local dev runs stay green.
_STOCKFISH_AVAILABLE = _resolve_stockfish_path() is not None

pytestmark = pytest.mark.skipif(
    not _STOCKFISH_AVAILABLE,
    reason=(
        "Stockfish is not installed (STOCKFISH_PATH is not set and no "
        "stockfish binary is on PATH); these tests run in CI/staging only."
    ),
)


def test_stockfish_is_installed_and_accepts_uci() -> None:
    executable = _resolve_stockfish_path()

    assert executable is not None, (
        f"Stockfish is not installed or STOCKFISH_PATH={STOCKFISH_PATH!r} "
        "does not resolve to an executable"
    )
    assert os.access(executable, os.X_OK), f"Stockfish is not executable: {executable}"

    result = subprocess.run(
        [str(executable)],
        input="uci\nquit\n",
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )

    assert "uciok" in result.stdout, (
        f"Stockfish started but did not complete the UCI handshake: {result.stdout}"
    )


def test_stockfish_completes_ready_handshake_and_returns_a_legal_move() -> None:
    executable = _resolve_stockfish_path()

    assert executable is not None, (
        f"Stockfish is not installed or STOCKFISH_PATH={STOCKFISH_PATH!r} "
        "does not resolve to an executable"
    )

    engine = StockfishEngine(
        engine_path=executable,
        hash_mb=16,
        threads=1,
        default_depth=1,
        timeout=10,
    )
    board = chess.Board()
    try:
        best_move = engine.get_best_move(board.fen(), depth=1, skill_level=5)
    finally:
        engine.quit()

    move = chess.Move.from_uci(best_move)
    assert board.is_legal(move), f"Stockfish returned an illegal move: {best_move!r}"
