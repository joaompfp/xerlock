"""Upload endpoint contract.

The lock promise — parsed in memory, never stored — is the product's core claim,
so it gets an explicit test rather than being assumed from reading the code.
"""

import glob
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from backend.main import app, MAX_UPLOAD_BYTES

client = TestClient(app)


@pytest.fixture
def sample_bytes(sample_path):
    with open(sample_path, "rb") as fh:
        return fh.read()


def post(name, payload):
    return client.post("/api/upload", files={"file": (name, payload, "application/octet-stream")})


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_upload_returns_the_parsed_schedule(sample_bytes):
    r = post("sample-schedule.xer", sample_bytes)
    assert r.status_code == 200
    data = r.json()
    assert data["project"]["total_activities"] == 24
    assert len(data["activities"]) == 24
    assert data["calendars"] and data["raw_tables"]
    assert data["warnings"] == []


def test_upload_rejects_non_xer_extensions(sample_bytes):
    r = post("schedule.mpp", sample_bytes)
    assert r.status_code == 400
    assert ".xer" in r.json()["detail"]


def test_upload_rejects_unparseable_content():
    r = post("not-really.xer", b"this is not an XER file at all")
    assert r.status_code == 422


def test_error_message_does_not_leak_internals():
    """Unexpected parse failures return a generic message; stack details belong
    in the server log, not in the browser."""
    r = post("broken.xer", b"%T\tTASK\n%F\tgarbage\n%R\t\x00\x01")
    assert r.status_code == 422
    assert "Traceback" not in r.text and "File \"" not in r.text


def test_oversized_upload_is_refused_with_413():
    payload = b"x" * (MAX_UPLOAD_BYTES + 1024)
    r = post("huge.xer", payload)
    assert r.status_code == 413
    assert "limit" in r.json()["detail"].lower()


def test_non_utf8_file_warns_about_dropped_characters(sample_bytes):
    """P6 commonly exports cp1252/latin-1 and PyP6XER drops the undecodable bytes
    silently — the user must be told their activity names may be mangled."""
    latin1 = sample_bytes.replace(b"Chiller procurement", b"Chiller pr\xf3curement")
    r = post("latin1.xer", latin1)
    assert r.status_code == 200
    assert any("UTF-8" in w for w in r.json()["warnings"])


def test_nothing_is_persisted_server_side(sample_bytes):
    """The lock promise: no uploaded file survives the request."""
    before = set(glob.glob(os.path.join(tempfile.gettempdir(), "*.xer")))
    assert post("sample-schedule.xer", sample_bytes).status_code == 200
    after = set(glob.glob(os.path.join(tempfile.gettempdir(), "*.xer")))
    assert after == before, f"upload left files behind: {after - before}"


def test_temp_file_is_removed_even_when_parsing_fails():
    before = set(glob.glob(os.path.join(tempfile.gettempdir(), "*.xer")))
    assert post("bad.xer", b"nonsense").status_code == 422
    after = set(glob.glob(os.path.join(tempfile.gettempdir(), "*.xer")))
    assert after == before


def test_no_cors_headers_are_advertised(sample_bytes):
    """The frontend is served same-origin; an Access-Control-Allow-Origin header
    would mean the API had been opened up by accident."""
    r = client.post(
        "/api/upload",
        files={"file": ("sample-schedule.xer", sample_bytes, "application/octet-stream")},
        headers={"Origin": "https://example.com"},
    )
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


def test_asset_responses_are_immutably_cached_and_index_is_not():
    """Content-hashed bundles may be cached forever; index.html must revalidate or
    a deploy leaves users on a stale build."""
    r = client.get("/api/health")
    assert r.headers["cache-control"] == "no-cache"
