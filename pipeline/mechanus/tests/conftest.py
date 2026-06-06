import copy
import json
import sys
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG_ROOT))

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def monsters() -> dict:
    data = json.loads((FIXTURES / "monsters_2014.json").read_text(encoding="utf-8"))
    return data["monsters"]


@pytest.fixture()
def vrock(monsters) -> dict:
    return copy.deepcopy(monsters["vrock"])


@pytest.fixture()
def balor(monsters) -> dict:
    return copy.deepcopy(monsters["balor"])
