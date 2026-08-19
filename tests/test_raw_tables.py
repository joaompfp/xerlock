"""Raw XER table inspection.

The Tables tab is the audit surface: a reviewer uses it to check what the
submission actually contains rather than trusting any tool's interpretation.
That only holds if the parser reproduces the file verbatim — no reordering, no
silent row loss, no column drift.
"""

from backend.main import parse_raw_tables, RAW_TABLE_ROW_CAP

XER = "\n".join([
    "ERMHDR\t15.2\t2026-03-02\tProject\tADMIN\tdemo\tdbxDatabaseNoName\tProject Management\tEUR",
    "%T\tPROJECT",
    "%F\tproj_id\tproj_short_name",
    "%R\t1\tDEMO",
    "%T\tTASK",
    "%F\ttask_id\ttask_code\ttask_name",
    "%R\t10\tA-010\tFirst",
    "%R\t11\tA-020\tSecond",
    "%E",
])


def test_tables_and_fields_parse_verbatim():
    tables, _ = parse_raw_tables(XER)
    assert list(tables) == ["PROJECT", "TASK"]  # file order, not alphabetical
    assert tables["TASK"]["fields"] == ["task_id", "task_code", "task_name"]
    assert tables["TASK"]["rows"] == [["10", "A-010", "First"],
                                      ["11", "A-020", "Second"]]
    assert tables["TASK"]["row_count"] == 2
    assert tables["TASK"]["truncated"] is False


def test_ermhdr_exposes_p6_version_and_export_date():
    """Shown in the Tables header — provenance a reviewer cites."""
    _, ermhdr = parse_raw_tables(XER)
    assert ermhdr["version"] == "15.2"
    assert ermhdr["export_date"] == "2026-03-02"
    assert ermhdr["fields"][0] == "15.2"


def test_rows_are_padded_and_trimmed_to_the_field_count():
    """Ragged rows would misalign every column to the right of the gap."""
    ragged = "\n".join([
        "%T\tTASK",
        "%F\ta\tb\tc",
        "%R\t1\t2",           # short
        "%R\t1\t2\t3\t4",     # long
    ])
    tables, _ = parse_raw_tables(ragged)
    assert tables["TASK"]["rows"] == [["1", "2", ""], ["1", "2", "3"]]


def test_empty_fields_are_preserved_not_dropped():
    tables, _ = parse_raw_tables("%T\tT\n%F\ta\tb\tc\n%R\t1\t\t3")
    assert tables["T"]["rows"] == [["1", "", "3"]]


def test_row_cap_truncates_but_reports_the_true_count():
    """Silent truncation would read as 'this is the whole table'."""
    over = RAW_TABLE_ROW_CAP + 5
    lines = ["%T\tBIG", "%F\tn"] + [f"%R\t{i}" for i in range(over)]
    tables, _ = parse_raw_tables("\n".join(lines))
    big = tables["BIG"]
    assert big["row_count"] == over
    assert len(big["rows"]) == RAW_TABLE_ROW_CAP
    assert big["truncated"] is True


def test_file_without_ermhdr_still_parses():
    tables, ermhdr = parse_raw_tables("%T\tT\n%F\ta\n%R\t1")
    assert tables["T"]["row_count"] == 1
    assert ermhdr == {}


def test_rows_before_any_table_header_are_ignored():
    tables, _ = parse_raw_tables("%R\t1\t2\n%T\tT\n%F\ta\n%R\t9")
    assert tables["T"]["rows"] == [["9"]]


# ── Against the shipped sample ───────────────────────────────────────────────

def test_sample_raw_tables(schedule):
    tables = schedule.raw_tables
    assert set(tables) == {"CALENDAR", "PROJECT", "PROJWBS", "TASK", "TASKPRED"}
    assert tables["TASK"]["row_count"] == 24
    assert tables["PROJWBS"]["row_count"] == 7
    assert not any(t["truncated"] for t in tables.values())


def test_raw_task_rows_agree_with_the_parsed_activities(schedule):
    """The inspector and the rest of the app must not disagree about the file."""
    task = schedule.raw_tables["TASK"]
    idx = task["fields"].index("task_code")
    raw_codes = {r[idx] for r in task["rows"]}
    assert raw_codes == {a["task_code"] for a in schedule.activities}


def test_sample_ermhdr(schedule):
    assert schedule.ermhdr["version"] == "15.2"
    assert schedule.ermhdr["export_date"] == "2026-03-02"
