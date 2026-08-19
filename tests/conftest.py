"""Shared fixtures.

Every test runs against `examples/sample-schedule.xer` — the synthetic 24-activity
data-centre fit-out that ships with the repo. Never point these at a real client
schedule: the sample is the only file that may appear in this repository.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

SAMPLE_XER = REPO_ROOT / "examples" / "sample-schedule.xer"


@pytest.fixture(scope="session")
def sample_path() -> str:
    assert SAMPLE_XER.exists(), f"sample schedule missing at {SAMPLE_XER}"
    return str(SAMPLE_XER)


@pytest.fixture(scope="session")
def schedule(sample_path):
    """Parsed sample schedule. Session-scoped: parsing is the expensive step and
    nothing in the suite mutates the result."""
    from backend.main import parse_xer

    return parse_xer(sample_path)


@pytest.fixture(scope="session")
def by_code(schedule):
    """Activities keyed by task_code — the stable identifier across re-exports."""
    return {a["task_code"]: a for a in schedule.activities}
