"""Oracle files kept locally under examples/ (gitignored `*.mpp`: Microsoft's own Project
templates and a third party's coursework, never committed). Each must reproduce with 0
differences and pass the Critical Path Test. Skipped when a file or the Java runtime
MPXJ needs is absent, so CI and other checkouts are unaffected; aggregates only."""

import pytest

from backend.schedule import parse_schedule
from tests.conftest import REPO_ROOT

pytest.importorskip("jpype")

EXAMPLES = REPO_ROOT / "examples"
ORACLE_FILES = {
    # file name prefix: (scheduled tasks, what it validates); a prefix, so no file name
    # carries its author's identifiers into the repository
    "Commercial construction project plan": (126, "lags, constraints, no progress"),
    "Microsoft Office Project 2003 deployment": (250, "summary-task logic and the free slack of tasks linked through summaries"),
    "MS Project Part 2": (22, "progress with a status date, and a task levelling delay"),
}


@pytest.mark.parametrize("name", sorted(ORACLE_FILES))
def test_example_mpp_reproduces_and_passes_the_critical_path_test(name):
    path = next(iter(sorted(EXAMPLES.glob(f"{name}*.mpp"))), None)
    if path is None:
        pytest.skip(f"{name} is not present (local oracle file)")
    d = parse_schedule(str(path))
    r = d["project"]["recalculation"]
    cpt = d["project"]["critical_path_test"]
    expected, _ = ORACLE_FILES[name]
    assert r["supported"], r["reason"]
    assert r["compared"] == expected
    assert r["differing"] == 0, r["by_field"]
    assert r["uncovered"] == []
    assert cpt and cpt["passed"] and cpt["exact"]
