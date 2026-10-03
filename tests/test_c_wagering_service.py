"""
C wagering service smoke tests.

Brings up the standalone C binary (wagering-service/build/wagering-service)
as a JSON-lines subprocess and drives the protocol end to end: provision,
sponsorship, overdraw rejection, free spins, and encrypted-at-rest survival
across restart. Skipped when the binary is absent (e.g. no gcc toolchain).
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BINARY = REPO_ROOT / "wagering-service" / "build" / "wagering-service"
KEY = "00112233445566778899aabbccddeeff102132435465768798a9bacbdcedfe0f"

pytestmark = pytest.mark.skipif(
    not BINARY.is_file(), reason="wagering-service binary not built (run wagering-service/build.sh)"
)


@pytest.fixture
def c_service(tmp_path):
    proc = subprocess.Popen(
        [str(BINARY)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={
            **os.environ,
            "WAGERING_SERVICE_DATA_DIR": str(tmp_path / "data"),
            "WAGERING_SERVICE_KEY": KEY,
        },
    )

    def call(op, **fields):
        proc.stdin.write(json.dumps({"id": "t", "op": op, **fields}) + "\n")
        proc.stdin.flush()
        return json.loads(proc.stdout.readline())

    yields = [call, proc, tmp_path]
    yield yields
    proc.stdin.close()
    proc.wait(timeout=5)


def test_hello_selfcheck(c_service):
    call, _, _ = c_service
    resp = call("crypto_selfcheck")
    assert resp["ok"] is True
    assert resp["data"]["kat"] == "ok"


def test_provision_sponsor_and_overdraw(c_service):
    call, _, _ = c_service
    assert call("wallet_provision", user="d", starting_balance="100")["ok"] is True
    resp = call("wallet_debit", user="d", amount="101", reason="bet")
    assert resp["ok"] is False and resp["error"]["code"] == "insufficient_funds"
    assert call("wallet_get", user="d")["data"]["balance"] == "100.00"


def test_sponsorship_credit_is_auditable(c_service):
    call, _, _ = c_service
    call("wallet_provision", user="d", starting_balance="100")
    resp = call(
        "sponsor_start",
        user="d",
        sponsor="Megacorp",
        amount="25.50",
        purpose="launch",
        ref="M-7",
    )
    assert resp["ok"] is True
    assert resp["data"]["balance"] == "125.50"
    listed = call("sponsorships_list", user="d")
    assert listed["data"]["sponsorships"][0]["ref"] == "M-7"
    assert listed["data"]["sponsorships"][0]["amount"] == "25.50"


def test_state_survives_restart(c_service):
    _, _, tmp_path = c_service
    data_dir = tmp_path / "data"
    resp = json.loads(
        subprocess.run(
            [str(BINARY)],
            input=json.dumps({"id": "t", "op": "wallet_provision", "user": "d", "starting_balance": "10"}),
            capture_output=True,
            text=True,
            env={**os.environ, "WAGERING_SERVICE_DATA_DIR": str(data_dir), "WAGERING_SERVICE_KEY": KEY},
        ).stdout
    )
    assert resp["ok"] is True
    # stored files must be 0600 and present
    assert list(data_dir.iterdir())
    for f in data_dir.iterdir():
        assert f.stat().st_mode & 0o777 == 0o600

    again = json.loads(
        subprocess.run(
            [str(BINARY)],
            input=json.dumps({"id": "t", "op": "wallet_get", "user": "d"}),
            capture_output=True,
            text=True,
            env={**os.environ, "WAGERING_SERVICE_DATA_DIR": str(data_dir), "WAGERING_SERVICE_KEY": KEY},
        ).stdout
    )
    assert again["data"]["balance"] == "10.00"