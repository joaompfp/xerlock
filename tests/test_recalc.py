"""The recalculation report around the CPM engine: how P6's scheduling options are read,
when the engine declines a file (and says why), and how stored dates that the engine
does not reproduce are reported. tests/test_cpm*.py cover the engine's rules; these
cover what backend/recalc.py does with a file.

Each test edits one field of examples/sample-schedule.xer, so a failure points at one rule.
"""

from pathlib import Path

import pytest

from backend import recalc
from backend.xer import parse_xer

SAMPLE = Path(__file__).resolve().parent.parent / "examples" / "sample-schedule.xer"


class Xer:
    """The sample as editable tables: field values set by name, rows added, written back."""

    def __init__(self):
        self.order, self.tables, self.head = [], {}, []
        cur = None
        for line in SAMPLE.read_text(encoding="utf-8").split("\n"):
            parts = line.split("\t")
            if parts[0] == "%T":
                cur = parts[1]
                self.order.append(cur)
                self.tables[cur] = {"fields": [], "rows": []}
            elif parts[0] == "%F":
                self.tables[cur]["fields"] = parts[1:]
            elif parts[0] == "%R":
                self.tables[cur]["rows"].append(parts[1:])
            elif cur is None and line:
                self.head.append(line)

    def set(self, table, field, value, where=None):
        t = self.tables[table]
        i = t["fields"].index(field)
        for row in t["rows"]:
            if where is None or row[t["fields"].index(where[0])] == where[1]:
                row[i] = value
        return self

    def get(self, table, field, where):
        t = self.tables[table]
        row = next(r for r in t["rows"] if r[t["fields"].index(where[0])] == where[1])
        return row[t["fields"].index(field)]

    def add(self, table, **values):
        t = self.tables[table]
        t["rows"].append([str(values.get(f, "")) for f in t["fields"]])
        return self

    def parse(self, tmp_path):
        out = list(self.head)
        for name in self.order:
            t = self.tables[name]
            out += [f"%T\t{name}", "%F\t" + "\t".join(t["fields"])] + ["%R\t" + "\t".join(r) for r in t["rows"]]
        f = tmp_path / "edited.xer"
        f.write_text("\n".join(out + ["%E", ""]), encoding="utf-8")
        return parse_xer(str(f))["project"]


def report(project):
    return project["recalculation"]


# ── Options ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("override, retained, mode", [
    ("Y", "N", "override"),
    ("N", "Y", "retained"),
    ("N", "N", "actual"),
])
def test_progress_mode_is_read_from_the_two_p6_flags(override, retained, mode):
    sched = {"sched_progress_override": override, "sched_retained_logic": retained}
    _, _, opts = recalc.engine_input([], [], {"proj_id": "1"}, sched)
    assert opts.progress_mode == mode


def test_missing_options_default_to_p6s_own_defaults():
    _, _, opts = recalc.engine_input([], [], {"proj_id": "1"}, {})
    assert (opts.progress_mode, opts.float_type, opts.lag_calendar) == ("retained", "FT_FF", "rcal_Predecessor")


# ── Files the engine declines ──────────────────────────────────────────────────

def test_no_data_date_is_declined_with_the_reason(tmp_path):
    r = report(Xer().set("PROJECT", "last_recalc_date", "").parse(tmp_path))
    assert r["supported"] is False and "no data date" in r["reason"]


def test_resource_dependent_activities_are_declined(tmp_path):
    x = Xer()
    code = x.tables["TASK"]["rows"][3][x.tables["TASK"]["fields"].index("task_code")]
    r = report(x.set("TASK", "task_type", "TT_Rsrc", where=("task_code", code)).parse(tmp_path))
    assert r["supported"] is False and "TT_Rsrc" in r["reason"]


def test_a_relationship_to_another_project_is_declined(tmp_path):
    x = Xer()
    pid = x.tables["PROJECT"]["rows"][0][x.tables["PROJECT"]["fields"].index("proj_id")]
    succ = x.tables["TASK"]["rows"][5][x.tables["TASK"]["fields"].index("task_id")]
    x.add("TASKPRED", task_pred_id=999001, task_id=succ, pred_task_id=888888, proj_id=pid,
          pred_proj_id=777, pred_type="PR_FS", lag_hr_cnt=0)
    r = report(x.parse(tmp_path))
    assert r["supported"] is False and "outside this project" in r["reason"]


def test_multiple_float_path_runs_are_declined(tmp_path):
    x = Xer()
    if "enable_multiple_longest_path_calc" not in x.tables["SCHEDOPTIONS"]["fields"]:
        pytest.skip("sample SCHEDOPTIONS has no multiple-float-path field")
    r = report(x.set("SCHEDOPTIONS", "enable_multiple_longest_path_calc", "Y").parse(tmp_path))
    assert r["supported"] is False and "multiple float path" in r["reason"]


def test_a_logic_loop_is_reported_not_raised(tmp_path):
    x = Xer()
    t = x.tables["TASKPRED"]
    first = t["rows"][0]
    pid = first[t["fields"].index("proj_id")]
    # The reverse of an existing link closes a loop.
    x.add("TASKPRED", task_pred_id=999002, task_id=first[t["fields"].index("pred_task_id")],
          pred_task_id=first[t["fields"].index("task_id")], proj_id=pid, pred_proj_id=pid,
          pred_type="PR_FS", lag_hr_cnt=0)
    r = report(x.parse(tmp_path))
    assert r["supported"] is False and "loop" in r["reason"].lower()


# ── Stored dates the engine does not reproduce ─────────────────────────────────

def _moved_finish(x, code):
    """The sample with one activity's stored early finish a week later than P6's."""
    from datetime import datetime, timedelta
    ef = x.get("TASK", "early_end_date", ("task_code", code))
    later = (datetime.fromisoformat(ef) + timedelta(days=7)).strftime("%Y-%m-%d %H:%M")
    return x.set("TASK", "early_end_date", later, where=("task_code", code))


def test_a_stored_date_that_differs_is_listed_and_skips_the_cpt(tmp_path):
    x = Xer()
    code = next(r[x.tables["TASK"]["fields"].index("task_code")] for r in x.tables["TASK"]["rows"]
                if r[x.tables["TASK"]["fields"].index("status_code")] == "TK_NotStart")
    project = _moved_finish(x, code).parse(tmp_path)
    r = report(project)
    assert r["supported"] is True
    assert r["differing"] == 1 and r["by_field"]["ef"] == 1
    assert [d["field"] for d in r["differences"]] == ["ef"]
    # The Critical Path Test only runs on a schedule the engine reproduces.
    assert project["critical_path_test"] is None


def test_the_differences_list_is_capped_but_the_count_is_not(tmp_path, monkeypatch):
    monkeypatch.setattr(recalc, "MAX_DIFFERENCES_LISTED", 1)
    x = Xer()
    f = x.tables["TASK"]["fields"]
    for row in [r for r in x.tables["TASK"]["rows"] if r[f.index("status_code")] == "TK_NotStart"][:3]:
        _moved_finish(x, row[f.index("task_code")])
    r = report(x.parse(tmp_path))
    assert r["differing"] == 3
    assert len(r["differences"]) == 1 and r["truncated"] is True
