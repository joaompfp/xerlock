"""Primavera P6 XML: the same schedule as the .xer it was exported beside, read by the
same rules (backend/pmxml.py maps the XML onto the .xer's tables).

The twin is the sample .xer written as P6 XML (tests/pmxml_twin.py). Everything that
carries meaning must match: activities, dates, float, links, codes, calendars, the
recalculation and the Critical Path Test. What may differ is only what the formats
themselves differ in: the file kind, and the WBS root (a .xer has a root WBS row of
its own; in P6 XML the project is the root)."""

from pathlib import Path

import pytest

from backend.pmxml import _hhmm_end, parse_pmxml
from backend.schedule import parse_schedule
from backend.xer import parse_xer
from tests.pmxml_twin import write_twin

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "examples" / "sample-schedule.xer"
CORPUS = ROOT / ".corpus" / "mpxj" / "junit" / "data"


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    twin = write_twin(SAMPLE, tmp_path_factory.mktemp("pmxml") / "sample.xml")
    return parse_xer(str(SAMPLE)), parse_schedule(str(twin)), twin


def _same_milestone(a, b):
    return {a, b} == {"TT_Mile", "TT_StartMile"}  # one P6 type, two .xer spellings


def test_activities_match_the_xer(pair):
    x, p, _ = pair
    assert len(x["activities"]) == len(p["activities"]) == 24
    for a, b in zip(x["activities"], p["activities"]):
        for k in a:
            if k == "task_type" and _same_milestone(a[k], b[k]):
                continue
            assert a[k] == b[k], (a["task_code"], k)


def test_scheduling_matches_the_xer(pair):
    x, p, _ = pair
    px, pp = x["project"], p["project"]
    for k in px:
        if k in ("source_format",):
            continue
        if k == "schedule_options":
            # The XML has no counterpart for the .xer's external-relationships option.
            assert {**px[k], "external_relationships": ""} == pp[k]
            continue
        assert px[k] == pp[k], k
    assert pp["source_format"] == "pmxml"
    assert pp["recalculation"]["supported"] and pp["recalculation"]["differing"] == 0
    assert pp["critical_path_test"]["passed"]


def test_calendars_and_wbs_match_the_xer(pair):
    x, p, _ = pair
    assert x["calendars"] == p["calendars"]
    strip = lambda n: {k: v for k, v in n.items() if k not in ("wbs_id", "parent_wbs_id", "seq_num", "wbs_short_name", "children")}  # noqa: E731
    assert strip(x["wbs_tree"][0]) == strip(p["wbs_tree"][0])
    assert [strip(c) for c in x["wbs_tree"][0]["children"]] == [strip(c) for c in p["wbs_tree"][0]["children"]]


def test_the_inspector_shows_the_files_own_elements(pair):
    _, p, _ = pair
    tables = p["raw_tables"]
    assert {"Project", "WBS", "Activity", "Relationship", "Calendar"} <= set(tables)
    assert "TotalFloat" in tables["Activity"]["fields"]
    assert tables["Activity"]["row_count"] == 24


def test_period_ends_are_read_as_p6_writes_them():
    assert _hhmm_end("11:59:00") == "12:00"
    assert _hhmm_end("15:29:00") == "15:30"
    assert _hhmm_end("23:59:00") == "00:00"
    assert _hhmm_end("16:00:00") == "16:00"


def test_an_embedded_baseline_is_a_project_of_the_file(pair, tmp_path):
    _, _, twin = pair
    text = twin.read_text(encoding="utf-8")
    # The same project again, as a BaselineProject with its own ids.
    start, end = text.index("<ns0:Project>"), text.index("</ns0:Project>") + len("</ns0:Project>")
    base = text[start:end].replace("<ns0:Project>", "<ns0:BaselineProject>").replace("</ns0:Project>", "</ns0:BaselineProject>")
    base = base.replace("<ns0:ObjectId>1000</ns0:ObjectId>", "<ns0:ObjectId>2000</ns0:ObjectId>", 1)
    base = base.replace("<ns0:Id>DEMO-DC-01</ns0:Id>", "<ns0:Id>DEMO-BL</ns0:Id>", 1)
    base = base.replace("<ns0:ProjectObjectId>1000</ns0:ProjectObjectId>", "<ns0:ProjectObjectId>2000</ns0:ProjectObjectId>")
    f = tmp_path / "with-baseline.xml"
    f.write_text(text[:end] + base + text[end:], encoding="utf-8")
    d = parse_pmxml(str(f))
    assert [p["proj_short_name"] for p in d["project"]["projects_in_file"]] == ["DEMO-DC-01", "DEMO-BL"]
    assert parse_pmxml(str(f), 2000)["project"]["proj_short_name"] == "DEMO-BL"


def test_not_p6_xml_is_refused():
    with pytest.raises(ValueError, match="not a Primavera P6 XML"):
        parse_pmxml(b"<?xml version='1.0'?><Project/>")


@pytest.mark.skipif(not CORPUS.exists(), reason="MPXJ corpus not fetched (scripts/fetch_msp_corpus.sh)")
def test_corpus_p6_xml_files_are_read():
    files = [f for f in CORPUS.rglob("*") if f.suffix in (".xml", ".pmxml") and b"APIBusinessObjects" in f.read_bytes()[:4096]]
    assert files
    for f in files:
        d = parse_schedule(str(f))
        assert d["project"]["source_format"] == "pmxml", f.name
        assert d["activities"], f.name


def test_missing_total_float_is_worked_out_from_the_dates(pair, tmp_path):
    x, _, twin = pair
    import re
    stripped = re.sub(r"<ns0:TotalFloat>[^<]*</ns0:TotalFloat>", "", twin.read_text(encoding="utf-8"))
    f = tmp_path / "no-float.xml"
    f.write_text(stripped, encoding="utf-8")
    d = parse_pmxml(str(f))
    assert any("no total float" in w for w in d["warnings"])
    # Finish float from the dates equals the float P6 stored, wherever P6 stored one.
    for a, b in zip(x["activities"], d["activities"]):
        if a["total_float_hrs"] is not None and a["early_end"] and a["late_end"]:
            assert b["total_float_hrs"] == pytest.approx(a["total_float_hrs"]), a["task_code"]
