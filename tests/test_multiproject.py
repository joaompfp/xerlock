"""A .xer holding several projects (an embedded baseline is the usual case): the largest
is shown by default, any other can be asked for by id, and every response lists the
file's projects so the reader can switch."""

from pathlib import Path

import pytest

from backend.xer import parse_xer
from backend.main import app

SAMPLE = Path(__file__).resolve().parent.parent / "examples" / "sample-schedule.xer"


def two_project_xer(tmp_path, kept=10):
    """The sample plus a second project: a copy of its WBS and first `kept` activities
    (and the links among them) under new ids, standing in for an embedded baseline."""
    lines = SAMPLE.read_text(encoding="utf-8").split("\n")
    tables, order, cur = {}, [], None
    for line in lines:
        p = line.split("\t")
        if p[0] == "%T":
            cur = p[1]; order.append(cur); tables[cur] = {"f": [], "r": []}
        elif p[0] == "%F":
            tables[cur]["f"] = p[1:]
        elif p[0] == "%R":
            tables[cur]["r"].append(p[1:])
    col = lambda t, n: tables[t]["f"].index(n)
    pid = tables["PROJECT"]["r"][0][col("PROJECT", "proj_id")]
    new = "999"
    proj = list(tables["PROJECT"]["r"][0])
    proj[col("PROJECT", "proj_id")] = new
    proj[col("PROJECT", "proj_short_name")] = "DEMO-BL"
    tables["PROJECT"]["r"].append(proj)
    wmap = {}
    for r in list(tables["PROJWBS"]["r"]):
        n = list(r)
        wmap[r[col("PROJWBS", "wbs_id")]] = str(90000 + len(wmap))
        n[col("PROJWBS", "wbs_id")] = wmap[r[col("PROJWBS", "wbs_id")]]
        n[col("PROJWBS", "proj_id")] = new
        tables["PROJWBS"]["r"].append(n)
    for r in tables["PROJWBS"]["r"][-len(wmap):]:
        parent = r[col("PROJWBS", "parent_wbs_id")]
        r[col("PROJWBS", "parent_wbs_id")] = wmap.get(parent, parent)
    tmap = {}
    for r in list(tables["TASK"]["r"])[:kept]:
        n = list(r)
        tmap[r[col("TASK", "task_id")]] = str(800000 + len(tmap))
        n[col("TASK", "task_id")] = tmap[r[col("TASK", "task_id")]]
        n[col("TASK", "proj_id")] = new
        n[col("TASK", "wbs_id")] = wmap.get(r[col("TASK", "wbs_id")], r[col("TASK", "wbs_id")])
        tables["TASK"]["r"].append(n)
    for i, r in enumerate(list(tables["TASKPRED"]["r"])):
        a, b = r[col("TASKPRED", "task_id")], r[col("TASKPRED", "pred_task_id")]
        if a in tmap and b in tmap:
            n = list(r)
            n[col("TASKPRED", "task_pred_id")] = str(700000 + i)
            n[col("TASKPRED", "task_id")], n[col("TASKPRED", "pred_task_id")] = tmap[a], tmap[b]
            n[col("TASKPRED", "proj_id")] = n[col("TASKPRED", "pred_proj_id")] = new
            tables["TASKPRED"]["r"].append(n)
    out = [l for l in lines if l.startswith("ERMHDR")]
    for t in order:
        out += [f"%T\t{t}", "%F\t" + "\t".join(tables[t]["f"])] + ["%R\t" + "\t".join(r) for r in tables[t]["r"]]
    f = tmp_path / "two.xer"
    f.write_text("\n".join(out + ["%E", ""]), encoding="utf-8")
    return f, int(pid)


def test_the_largest_project_is_shown_and_every_project_listed(tmp_path):
    f, pid = two_project_xer(tmp_path)
    d = parse_xer(str(f))
    assert d["project"]["proj_id"] == pid
    assert len(d["activities"]) == 24
    assert [(p["proj_short_name"], p["activities"]) for p in d["project"]["projects_in_file"]] == [("DEMO-DC-01", 24), ("DEMO-BL", 10)]
    assert "the largest" in d["warnings"][0]


def test_another_project_can_be_asked_for(tmp_path):
    f, _ = two_project_xer(tmp_path)
    d = parse_xer(str(f), 999)
    assert d["project"]["proj_short_name"] == "DEMO-BL"
    assert len(d["activities"]) == 10
    assert d["project"]["proj_id"] == 999
    # Its links are its own: a project's relationships never reach into the other.
    ids = {a["task_id"] for a in d["activities"]}
    assert all(p["task_id"] in ids for a in d["activities"] for p in a["predecessors"])


def test_an_unknown_project_is_refused(tmp_path):
    f, _ = two_project_xer(tmp_path)
    with pytest.raises(ValueError, match="no project with id 4242"):
        parse_xer(str(f), 4242)


def test_the_upload_takes_a_project(tmp_path):
    from fastapi.testclient import TestClient
    f, _ = two_project_xer(tmp_path)
    r = TestClient(app).post("/api/upload", files={"file": ("two.xer", f.read_bytes())}, data={"project": "999"})
    assert r.status_code == 200
    assert r.json()["project"]["proj_short_name"] == "DEMO-BL"
