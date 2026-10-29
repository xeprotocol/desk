import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]
NETWORK_ID = "testnet-0005"


@pytest.fixture(scope="session")
def blocks() -> dict:
    return json.loads((FIXTURES / "blocks.json").read_text())


@pytest.fixture(scope="session")
def statechain() -> dict:
    return json.loads((FIXTURES / "statechain.json").read_text())


@pytest.fixture(scope="session")
def config():
    from desk.config import load_config

    return load_config(ROOT / "config")


@pytest.fixture(scope="session")
def triage_text() -> str:
    """The real triage doc. It carries private reports, so it is not in the repo; tests that need it are
    skipped where it is absent. Point DESK_TRIAGE_DOC at a copy to run them."""
    import os

    path = Path(os.environ.get("DESK_TRIAGE_DOC") or ROOT / "docs" / "BOUNTY_TRIAGE.md")
    if not path.exists():
        pytest.skip("docs/BOUNTY_TRIAGE.md is not in the repo (private reports); set DESK_TRIAGE_DOC")
    return path.read_text(encoding="utf-8")
