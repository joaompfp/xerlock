"""The .mpp path (backend/mpp.py): MPXJ converts the file to MSPDI in memory and the
MSPDI reader reads that. Needs a JRE: skipped without one (CI installs one).

No .mpp can be committed (the only ones to hand are MPXJ's test data, fetched by
scripts/fetch_msp_corpus.sh, and client files), so the always-on test round-trips the
XML sample through MPXJ, which exercises the JVM start, the reader and the writer the
.mpp path uses. The tests on real .mpp files run when the corpus is present.
"""

import shutil

import pytest

from backend.schedule import parse_schedule
from tests.conftest import REPO_ROOT

SAMPLE_XML = REPO_ROOT / "examples" / "sample-schedule.xml"
CORPUS = REPO_ROOT / ".corpus" / "mpxj" / "junit" / "data"


def _java_available():
    try:
        import jpype
        return bool(jpype.getDefaultJVMPath())
    except Exception:
        return shutil.which("java") is not None


java = pytest.mark.skipif(not _java_available(), reason="no Java runtime for MPXJ")
corpus = pytest.mark.skipif(not CORPUS.exists(), reason="MPXJ corpus not fetched (scripts/fetch_msp_corpus.sh)")


def core(data):
    return [(a["task_id"], a["early_start"], a["early_end"], a["late_start"], a["late_end"], a["status"],
             a["task_type"], a["cstr_type"], a["is_longest_path"],
             [(p["task_id"], p["type"], p["lag_hrs"], p["driving"]) for p in a["predecessors"]])
            for a in data["activities"]]


@java
def test_mpxj_round_trip_of_the_sample_reads_the_same_schedule():
    from backend import mpp, mspdi
    xml = mpp.to_mspdi(str(SAMPLE_XML))
    assert xml.startswith(b"<?xml") and b"schemas.microsoft.com/project" in xml[:300]
    via_mpxj = mspdi.parse_mspdi(xml, source_format="mpp")
    direct = parse_schedule(str(SAMPLE_XML))
    assert via_mpxj["project"]["source_format"] == "mpp"
    assert via_mpxj["project"]["total_activities"] == direct["project"]["total_activities"] == 24
    assert via_mpxj["project"]["data_date"] == direct["project"]["data_date"]
    assert core(via_mpxj) == core(direct)
    assert via_mpxj["calendars"][0]["exceptions"] == direct["calendars"][0]["exceptions"]


@java
def test_unreadable_file_is_refused_with_mpxjs_reason(tmp_path):
    from backend import mpp
    p = tmp_path / "x.mpp"
    p.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 4096)
    with pytest.raises(ValueError, match="MPXJ"):
        mpp.to_mspdi(str(p))


@java
@corpus
def test_corpus_mpp_agrees_with_its_mspdi_twin():
    """Project 2019 saved the same project both ways; both paths must read the same
    dates, links and Longest Path. (MPXJ writes no TotalSlack where the .mpp stores
    none, so float is compared by the corpus script, not here.)"""
    d = CORPUS / "generated" / "task-links"
    via_mpp = parse_schedule(str(d / "task-links-project2019-mpp14.mpp"))
    via_xml = parse_schedule(str(d / "task-links-project2019-mspdi.xml"))
    assert via_mpp["project"]["source_format"] == "mpp"
    assert core(via_mpp) == core(via_xml)


@java
@corpus
def test_corpus_project_98_file_is_read():
    d = parse_schedule(str(CORPUS / "generated" / "task-links" / "task-links-project98-mpp8.mpp"))
    assert d["project"]["total_activities"] == 16


@java
@corpus
def test_corpus_password_protected_file_is_refused_with_a_reason():
    with pytest.raises(ValueError, match="password"):
        parse_schedule(str(next(CORPUS.rglob("password*.mpp"))))
