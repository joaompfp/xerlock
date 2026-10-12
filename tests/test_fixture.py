"""The frontend health-check tests run on a JSON snapshot of the sample's parse. If the
parser changes, the snapshot must change with it, or the frontend is tested against
data the backend no longer produces."""

import json

from tests.conftest import REPO_ROOT

FIXTURE = REPO_ROOT / "frontend" / "src" / "utils" / "fixtures" / "sample-schedule.json"


def current(schedule):
    d = schedule.model_dump()
    return {"project": d["project"], "activities": d["activities"]}


def test_frontend_fixture_matches_the_parser(schedule):
    expected = current(schedule)
    actual = json.loads(FIXTURE.read_text())
    assert actual == json.loads(json.dumps(expected)), (
        "frontend fixture is stale; regenerate with:\n"
        "  python -c \"import json; from backend.main import parse_xer; "
        "d=parse_xer('examples/sample-schedule.xer').model_dump(); "
        "json.dump({'project':d['project'],'activities':d['activities']}, "
        "open('frontend/src/utils/fixtures/sample-schedule.json','w'), indent=1)\""
    )
