"""Cross-language integration tests for the Java MMO game service.

These tests build and boot the real ``mmo-server`` jar (JDK-only + the vendored
SQLite driver), drive its HTTP API, and assert the two Ps the feature is built
around — **Persistence** and the **shared wallet**:

1. World/player state survives a full service restart.
2. The MMO's wealth is written as wallet domain events into the ``casino_events``
   SQLite store in the Python-era event schema (the schema the retired
   ``boombot.casino`` wallet used, and the schema a future C++20 adapter would
   replay).

Skipped when ``java`` is unavailable or the jar cannot be built, so the pure
Python test suite still runs anywhere.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MMO_SERVER = REPO_ROOT / "mmo-server"
SQLITE_JAR = "sqlite-jdbc-3.43.0.0.jar"

pytestmark = pytest.mark.skipif(
    shutil.which("java") is None,
    reason="java is required to run the MMO game service",
)


def _have_jar() -> bool:
    return (MMO_SERVER / "build" / "mmo-server.jar").exists()


def _ensure_built() -> None:
    if _have_jar():
        return
    r = subprocess.run(["bash", str(MMO_SERVER / "build.sh")], cwd=str(REPO_ROOT))
    if r.returncode != 0 or not _have_jar():
        pytest.skip("could not build the MMO game service (check ./build.sh)")


def _call(base, token, path, body=None):
    url = base + path
    if token:
        url += ("&" if "?" in path else "?") + "token=" + token
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"error": str(e)}


class MmoServer:
    """A running mmo-server instance backed by throwaway SQLite files."""

    def __init__(self, tmp, game, wallet, port):
        _ensure_built()
        self.base = f"http://127.0.0.1:{port}"
        env = dict(os.environ, MMO_PORT=str(port), MMO_BIND="127.0.0.1",
                   MMO_GAME_DB=str(game), MMO_WALLET_DB=str(wallet))
        cp = str(MMO_SERVER / "build" / "mmo-server.jar") + ":" + str(
            MMO_SERVER / "build" / SQLITE_JAR)
        self.log = (tmp / "server.log").open("w")
        self.proc = subprocess.Popen(
            ["java", "-cp", cp, "com.boombot.mmo.MmoServerMain"],
            cwd=str(MMO_SERVER), env=env, stdout=self.log, stderr=subprocess.STDOUT)
        self._wait_ready()

    def _wait_ready(self):
        for _ in range(80):
            try:
                if _call(self.base, None, "/api/world")[0] == 200:
                    return
            except Exception:
                pass
            time.sleep(0.25)
        self.stop()
        raise RuntimeError("MMO server did not become ready:\n"
                           + open(self.log.name).read())

    def call(self, path, body=None, token=None):
        return _call(self.base, token, path, body)

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def _gather_one(server, token):
    """Walk to a reachable tree and gather until a log drops into the inventory.

    The first log only appears after a full gather tick (~1.2s), so we keep
    polling until the item is actually in hand — callers can then sell it.
    If the nearest tree is unreachable (blocked by a rock/lake), fall back to
    the next nearest one.
    """
    _, g = server.call("/api/game", token=token)
    trees = sorted(
        (r for r in g["resources"] if r["type"] == "tree"),
        key=lambda q: (q["x"] - g["you"]["x"]) ** 2 + (q["y"] - g["you"]["y"]) ** 2,
    )
    if not trees:
        raise AssertionError("world has no trees to gather")
    target = trees[0]
    server.call("/api/move", {"token": token, "x": target["x"], "y": target["y"]})
    gathering = False
    for _ in range(300):
        _, gg = server.call("/api/game", token=token)
        you = gg["you"]
        in_range = (you["x"] - target["x"]) ** 2 + (you["y"] - target["y"]) ** 2 <= 9
        if not gathering and in_range:
            server.call("/api/gather", {"token": token, "resourceId": target["id"]})
            gathering = True
        if gathering and you["inventory"].get("logs", 0) > 0:
            return
        if not gathering and not you["moving"] and not in_range:
            trees = [t for t in trees if t["id"] != target["id"]]
            if not trees:
                raise AssertionError("no tree was reachable")
            target = trees[0]
            server.call("/api/move", {"token": token, "x": target["x"], "y": target["y"]})
        time.sleep(0.2)
    raise AssertionError("timed out trying to gather a log")
def test_server_serves_client_and_world(tmp_path):
    server = MmoServer(tmp_path, tmp_path / "g.sqlite3", tmp_path / "w.sqlite3", 8141)
    try:
        st, world = server.call("/api/world")
        assert st == 200
        assert world["w"] == 72 and world["h"] == 72
        assert len(world["tiles"]) == 72 * 72
    finally:
        server.stop()


def test_persistence_across_restart_and_shared_wallet(tmp_path):
    game = tmp_path / "game.sqlite3"
    wallet = tmp_path / "wallet.sqlite3"

    # --- first life ---------------------------------------------------------
    s1 = MmoServer(tmp_path, game, wallet, 8142)
    try:
        _, join = s1.call("/api/join", {"name": "PersistGuy"})
        token = join["token"]
        _gather_one(s1, token)
        _, g = s1.call("/api/game", token=token)
        logs = g["you"]["inventory"].get("logs", 0)
        if logs:
            s1.call("/api/sell", {"token": token, "item": "logs", "qty": logs})
        _, g = s1.call("/api/game", token=token)
        assert g["you"]["walletCents"] > 0, "selling should credit the wallet"
        pos1 = (g["you"]["x"], g["you"]["y"])
        wood_xp1 = g["you"]["woodcuttingXp"]
    finally:
        s1.stop()

    # --- second life: same DB files, freshly restarted service -------------
    s2 = MmoServer(tmp_path, game, wallet, 8143)
    try:
        _, resume = s2.call("/api/join", {"name": "PersistGuy", "token": token})
        assert resume["token"] == token, "resuming with a token must reload the player"
        _, g = s2.call("/api/game", token=token)
        assert (g["you"]["x"], g["you"]["y"]) == pos1
        assert g["you"]["woodcuttingXp"] == wood_xp1
        assert g["you"]["walletCents"] > 0
    finally:
        s2.stop()


def test_python_can_replay_java_wallet_events(tmp_path):
    """Shared-wallet proof: Java appends Python-era events to casino_events."""
    game = tmp_path / "game.sqlite3"
    wallet = tmp_path / "wallet.sqlite3"
    server = MmoServer(tmp_path, game, wallet, 8144)
    java_balance = 0
    joined_id = None
    try:
        _, join = server.call("/api/join", {"name": "WalletGuy"})
        joined_id = join["id"]
        token = join["token"]
        _gather_one(server, token)
        _, g = server.call("/api/game", token=token)
        logs = g["you"]["inventory"].get("logs", 0)
        _, sell = server.call("/api/sell", {"token": token, "item": "logs",
                                            "qty": logs}) if logs else (0, {})
        java_balance = sell.get("walletCents", 0)
        assert java_balance > 0
    finally:
        server.stop()

    # Verify the append-only event log written by Java against the shared
    # schema: casino_events(event_id, aggregate_id, occurred_on, version,
    # event_type, payload_json). The retired Python wallet (boombot.casino)
    # used exactly this table; the balance Java reported must equal the sum
    # of the credited events.
    conn = sqlite3.connect(wallet)
    try:
        rows = conn.execute(
            "SELECT version, event_type, payload_json FROM casino_events "
            "WHERE aggregate_id = ? ORDER BY version ASC",
            ("mmo:" + joined_id,),
        ).fetchall()
    finally:
        conn.close()

    assert rows, "Java service wrote no wallet events"
    assert rows[0][1] == "WalletCreatedEvent"
    assert any(t == "FundsCreditedEvent" for _, t, _ in rows)

    credit_cents = sum(
        int(round(float(json.loads(payload)["payload"]["amount"]) * 100))
        for _, t, payload in rows
        if t == "FundsCreditedEvent"
    )
    assert credit_cents == java_balance, (
        f"replayed credits ({credit_cents}) != Java-reported balance ({java_balance})"
    )
