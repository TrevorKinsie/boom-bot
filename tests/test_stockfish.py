import os
import shutil
import subprocess
from pathlib import Path

from boombot.core.config import STOCKFISH_PATH


def _resolve_stockfish_path() -> Path | None:
    configured_path = Path(STOCKFISH_PATH)
    if configured_path.is_absolute():
        return configured_path if configured_path.is_file() else None

    resolved_path = shutil.which(STOCKFISH_PATH)
    return Path(resolved_path) if resolved_path else None


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
