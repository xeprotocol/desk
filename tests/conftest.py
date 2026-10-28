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
    return (ROOT / "docs" / "BOUNTY_TRIAGE.md").read_text(encoding="utf-8")
