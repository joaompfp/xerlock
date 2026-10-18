"""
XERlock's Microsoft Project reader: an MSPDI XML file (File > Save As > XML) in, the
neutral intermediate out (see analysis.build), and `parse_mspdi` for the full schedule
structure the API serves. A .mpp arrives here too, after backend/mpp.py has converted it
to MSPDI in memory.

Standard-library xml.etree only, so it runs on the server and in the browser under
Pyodide. Field codes and units follow Microsoft's MSPDI schema as MPXJ's MSPDIReader
reads them (org.mpxj.mspdi, DatatypeConverter, RecurringData); docs/METHODOLOGY.md
("Microsoft Project files") maps every field and check and gives the evidence for each
mapping decision.

Everything here is Project's own stored value: Start/Finish, LateStart/LateFinish,
TotalSlack/FreeSlack, Critical, actuals, Baseline 0, constraints and calendars are read
from the file, never recomputed. The recalculation is reported as not available.
"""

import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from backend import analysis, recalc

NS = "http://schemas.microsoft.com/project"
_T = "{%s}" % NS

RECALC_UNAVAILABLE = "not yet available for Microsoft Project files"

# MSPDI PredecessorLink/Type (MPXJ RelationType): 0 FF, 1 FS, 2 SF, 3 SS.
LINK_TYPES = {"0": "PR_FF", "1": "PR_FS", "2": "PR_SF", "3": "PR_SS"}

# MSPDI Task/ConstraintType (MPXJ ConstraintType). Must Start/Finish On map to P6's
# Mandatory constraints because Project holds the date against later logic and shows
# the conflict as negative slack (slack9.mpp in the MPXJ corpus: a Must Finish On
# milestone kept at its date while its predecessor finishes a day later); P6's Start/
# Finish On would let logic move the date instead. HonorConstraints cannot refine
# this: Project writes 0 and MPXJ 1 for the same project, so it is not read.
CONSTRAINT_TYPES = {
    "0": None,            # As Soon As Possible: no constraint in P6 terms
    "1": "CS_ALAP",       # As Late As Possible
    "2": "CS_MANDSTART",  # Must Start On
    "3": "CS_MANDFIN",    # Must Finish On
    "4": "CS_MSOA",       # Start No Earlier Than
    "5": "CS_MSOB",       # Start No Later Than
    "6": "CS_MEOA",       # Finish No Earlier Than
    "7": "CS_MEOB",       # Finish No Later Than
}

# LagFormat (MPXJ parseDurationTimeUnits): elapsed units count on the 24-hour clock,
# percent units are a share of the predecessor's duration. 35+ are the "estimated"
# variants of 3+ (the same unit, shown with a question mark).
ELAPSED_LAG_FORMATS = {"4", "6", "8", "10", "12", "20", "36", "38", "40", "42", "44", "52"}
PERCENT_LAG_FORMATS = {"19", "20", "51", "52"}

# MSPDI weekday DayType 1..7 = Sunday..Saturday, the same numbering P6 uses.
WEEKDAY_KEYS = [str(d) for d in range(1, 8)]

_DURATION_RE = re.compile(
    r"^(-)?P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$"
)


class UnsupportedFile(ValueError):
    """The file is XML but not MSPDI; the message says what it is and what to do."""


# ── Scalar decoding ───────────────────────────────────────────────────────────

def iso_duration_hours(value) -> Optional[float]:
    """An xsd:duration (PT40H0M0S) in hours. Project writes hours and minutes; days,
    months and years are converted as MPXJ converts them (24 h, 30 d, 365 d). A
    malformed value is ignored, as Project ignores it."""
    if not value:
        return None
    m = _DURATION_RE.match(value.strip())
    if not m:
        return None
    sign, y, mo, d, h, mi, s = m.groups()
    hours = (int(y or 0) * 365 * 24 + int(mo or 0) * 30 * 24 + int(d or 0) * 24
             + int(h or 0) + int(mi or 0) / 60 + float(s or 0) / 3600)
    return -hours if sign else hours


def tenths_of_minutes_hours(value) -> Optional[float]:
    """Slack and lag fields hold tenths of a minute (TotalSlack 4800 = 8 h)."""
    try:
        return int(value) / 600 if value not in (None, "") else None
    except ValueError:
        return None


def parse_date(value) -> Optional[datetime]:
    """MSPDI dates are ISO 8601 local times without a zone (2018-10-18T08:00:00)."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        return None


def _flag(value) -> Optional[bool]:
    return None if value in (None, "") else value.strip() in ("1", "true")


def _int(value, default=None):
    try:
        return int(value) if value not in (None, "") else default
    except ValueError:
        return default


def _getter(el):
    """Text of a named child of `el` (bound now, not when the loop variable moves on)."""
    return lambda name: el.findtext(_T + name)


def _hhmm(value) -> Optional[str]:
    """WorkingTime FromTime/ToTime (08:00:00) as the HH:MM the calendar model uses."""
    if not value or len(value) < 5:
        return None
    return value[:5]


# ── Calendars ─────────────────────────────────────────────────────────────────

def _periods_of(times_el):
    out = []
    if times_el is None:
        return out
    for wt in times_el.findall(_T + "WorkingTime"):
        s, f = _hhmm(wt.findtext(_T + "FromTime")), _hhmm(wt.findtext(_T + "ToTime"))
        if s and f:
            out.append({"start": s, "finish": f})
    return out


def _weekly_days(bitmap: int):
    """DaysOfWeek bitmap (MPXJ DAY_MASKS): bit 0 Sunday .. bit 6 Saturday, as Python
    weekday numbers (0 = Monday)."""
    return {(i + 6) % 7 for i in range(7) if bitmap & (1 << i)}


def _ordinal_weekday(first: date, weekday: int, number: int) -> date:
    """The number-th (1..4) given weekday on or after `first` (MPXJ getOrdinalRelativeDay)."""
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (number - 1))


def _last_weekday(first: date, weekday: int) -> date:
    """The last given weekday of the month containing `first` (MPXJ getLastRelativeDay)."""
    nxt = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    last = nxt - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def _clamp_day(y: int, m: int, day: int) -> date:
    nxt = _add_months(date(y, m, 1), 1)
    return date(y, m, min(day, (nxt - timedelta(days=1)).day))


def exception_dates(exc_el, start: date, finish: Optional[date]):
    """The dates one calendar exception covers, expanded the way MPXJ's RecurringData
    does from the MSPDI recurrence fields: Type 1 daily, 7 daily every Period days, 6
    weekly on the DaysOfWeek bitmap every Period weeks, 4/5 monthly on MonthDay or on
    the MonthPosition-th MonthItem weekday every Period months, 2/3 yearly likewise in
    Month. The range ends at ToDate when the file gives one, else after Occurrences."""
    g = lambda name: exc_el.findtext(_T + name)
    rtype = _int(g("Type"), 0)
    freq = max(1, _int(g("Period"), 1))
    occurrences = max(1, _int(g("Occurrences"), 1))
    dates = []

    def more(d):
        return (not d > finish) if finish else len(dates) < occurrences

    if rtype in (1, 7) or rtype not in (2, 3, 4, 5, 6):
        d = start
        step = freq if rtype == 7 else 1
        while more(d):
            dates.append(d)
            d += timedelta(days=step)
    elif rtype == 6:
        days = _weekly_days(_int(g("DaysOfWeek"), 0))
        if not days:
            return []
        week = start - timedelta(days=(start.weekday() + 1) % 7)  # the Sunday on or before
        while more(week):
            for offset in range(7):
                d = week + timedelta(days=offset)
                if d.weekday() in days:
                    if not more(d):
                        return dates
                    if d >= start:
                        dates.append(d)
            week += timedelta(days=7 * freq)
    elif rtype in (4, 5):
        if rtype == 5:
            weekday = (_int(g("MonthItem"), 2) - 2 + 6) % 7  # MonthItem 2..8 = Sunday..Saturday
            number = _int(g("MonthPosition"), 0) + 1
            first = start.replace(day=1)
            while more(first):
                d = _last_weekday(first, weekday) if number > 4 else _ordinal_weekday(first, weekday, number)
                if d >= start:
                    dates.append(d)
                    if not more(d):
                        break
                first = _add_months(first, freq)
        else:
            day = _int(g("MonthDay"), 1)
            first = start.replace(day=1)
            if day < start.day:
                first = _add_months(first, 1)
            while more(first):
                d = _clamp_day(first.year, first.month, day)
                dates.append(d)
                first = _add_months(first, freq)
    else:  # 2 yearly absolute, 3 yearly relative
        month = _int(g("Month"), 0) + 1
        first = date(start.year, month, 1)
        if rtype == 3:
            weekday = (_int(g("MonthItem"), 2) - 2 + 6) % 7
            number = _int(g("MonthPosition"), 0) + 1
            while more(first):
                d = _last_weekday(first, weekday) if number > 4 else _ordinal_weekday(first, weekday, number)
                if d >= start:
                    dates.append(d)
                    if not more(d):
                        break
                first = date(first.year + 1, first.month, 1)
        else:
            day = _int(g("MonthDay"), 1)
            while more(first):
                d = _clamp_day(first.year, first.month, day)
                if d < start:
                    d = _clamp_day(d.year + 1, d.month, day)
                dates.append(d)
                first = date(d.year + 1, d.month, 1)
    return dates


def _exceptions_of(cal_el):
    """{date: periods} from the calendar's own exceptions: the Exceptions list (Project
    2007 and later) when present, else the DayType 0 week-day entries older files use.
    Project writes both for the same exceptions; MPXJ reads the list first and ignores
    the legacy entries when it is non-empty, and so does this."""
    out = {}
    listed = cal_el.find(_T + "Exceptions")
    if listed is not None and len(listed):
        for exc in listed.findall(_T + "Exception"):
            tp = exc.find(_T + "TimePeriod")
            if tp is None:
                continue
            start = parse_date(tp.findtext(_T + "FromDate"))
            finish = parse_date(tp.findtext(_T + "ToDate"))
            if start is None and finish is None:
                continue
            start = (start or finish).date()
            working = _flag(exc.findtext(_T + "DayWorking"))
            periods = _periods_of(exc.find(_T + "WorkingTimes")) if working is not False else []
            for d in exception_dates(exc, start, finish.date() if finish else None):
                out[d] = periods
        return out
    for wd in cal_el.findall(f"{_T}WeekDays/{_T}WeekDay"):
        if wd.findtext(_T + "DayType") != "0":
            continue
        tp = wd.find(_T + "TimePeriod")
        if tp is None:
            continue
        start = parse_date(tp.findtext(_T + "FromDate"))
        finish = parse_date(tp.findtext(_T + "ToDate")) or start
        if start is None:
            continue
        working = _flag(wd.findtext(_T + "DayWorking"))
        periods = _periods_of(wd.find(_T + "WorkingTimes")) if working is not False else []
        d, last = start.date(), finish.date()
        while d <= last:
            out[d] = periods
            d += timedelta(days=1)
    return out


def read_calendars(root, default_uid: str, hrs_per_day: float, hrs_per_week: float):
    """Calendars in the decoded form the calendar model uses (weekday keys "1".."7" =
    Sunday..Saturday, dated exceptions), with a derived calendar inheriting the days and
    exceptions its base calendar defines and it does not override."""
    raw = {}
    order = []
    for cal in root.findall(f"{_T}Calendars/{_T}Calendar"):
        uid = (cal.findtext(_T + "UID") or "").strip()
        if not uid:
            continue
        days = {}
        for wd in cal.findall(f"{_T}WeekDays/{_T}WeekDay"):
            key = (wd.findtext(_T + "DayType") or "").strip()
            if key not in WEEKDAY_KEYS:
                continue
            working = _flag(wd.findtext(_T + "DayWorking"))
            days[key] = _periods_of(wd.find(_T + "WorkingTimes")) if working else []
        base = (cal.findtext(_T + "BaseCalendarUID") or "").strip()
        raw[uid] = {
            "name": cal.findtext(_T + "Name") or "",
            "is_base": _flag(cal.findtext(_T + "IsBaseCalendar")) is not False,
            "base": base if base not in ("", "-1", "0") or base in raw else None,
            "days": days,
            "exceptions": _exceptions_of(cal),
        }
        order.append(uid)

    resolved = {}

    def resolve(uid, seen=()):
        if uid in resolved:
            return resolved[uid]
        c = raw[uid]
        base = raw.get(c["base"]) and c["base"] not in seen and resolve(c["base"], seen + (uid,))
        weekdays = {k: list(base["weekdays"][k]) for k in WEEKDAY_KEYS} if base else {k: [] for k in WEEKDAY_KEYS}
        for k, periods in c["days"].items():
            weekdays[k] = periods
        exceptions = dict(base["exceptions"]) if base else {}
        exceptions.update(c["exceptions"])
        resolved[uid] = {"weekdays": weekdays, "exceptions": exceptions}
        return resolved[uid]

    out = []
    for uid in order:
        r = resolve(uid)
        out.append({
            "clndr_id": uid,
            "clndr_name": raw[uid]["name"],
            "clndr_type": "CA_Base" if raw[uid]["is_base"] else "CA_Rsrc",
            "default_flag": uid == default_uid,
            "day_hr_cnt": hrs_per_day,
            "week_hr_cnt": hrs_per_week,
            "weekdays": r["weekdays"],
            "exceptions": [{"date": d.isoformat(), "periods": p} for d, p in sorted(r["exceptions"].items())],
        })
    return out


# ── Raw tables ────────────────────────────────────────────────────────────────

def _local(tag):
    return tag.split("}", 1)[1] if "}" in tag else tag


def _simple_fields(el):
    """The record's leaf children: {element name: text}. Nested records are tables of
    their own (see raw_tables)."""
    out = {}
    for ch in el:
        if len(ch) == 0:
            out[_local(ch.tag)] = ch.text or ""
    return out


class _Table:
    def __init__(self):
        self.fields = []
        self.rows = []
        self.row_count = 0

    def add(self, record: dict):
        self.row_count += 1
        if self.row_count > analysis.RAW_TABLE_ROW_CAP:
            return
        for k in record:
            if k not in self.fields:
                self.fields.append(k)
        self.rows.append(record)

    def done(self):
        rows = [[r.get(f, "") for f in self.fields] for r in self.rows]
        return {"fields": self.fields, "rows": rows, "row_count": self.row_count,
                "truncated": self.row_count > analysis.RAW_TABLE_ROW_CAP}


def _working_times_text(el):
    return "; ".join(f"{p['start']}-{p['finish']}" for p in _periods_of(el))


def raw_tables(root) -> dict:
    """The XML's own records as tables, values verbatim: one table per record type,
    field names exactly as the element names. A nested record (a task's
    PredecessorLink, Baseline or ExtendedAttribute; a calendar's WeekDay or Exception)
    is a table of its own with its parent's UID as the first column. Period and date
    ranges inside calendar records are joined into one column each."""
    tables = {}

    def table(name):
        return tables.setdefault(name, _Table())

    table("Project").add(_simple_fields(root))
    for task in root.findall(f"{_T}Tasks/{_T}Task"):
        row = _simple_fields(task)
        table("Tasks").add(row)
        uid = row.get("UID", "")
        for link in task.findall(_T + "PredecessorLink"):
            table("PredecessorLinks").add({"TaskUID": uid, **_simple_fields(link)})
        for bl in task.findall(_T + "Baseline"):
            table("TaskBaselines").add({"TaskUID": uid, **_simple_fields(bl)})
        for ea in task.findall(_T + "ExtendedAttribute"):
            table("TaskExtendedAttributes").add({"TaskUID": uid, **_simple_fields(ea)})
    for cal in root.findall(f"{_T}Calendars/{_T}Calendar"):
        row = _simple_fields(cal)
        table("Calendars").add(row)
        uid = row.get("UID", "")
        for wd in cal.findall(f"{_T}WeekDays/{_T}WeekDay"):
            r = {"CalendarUID": uid, **_simple_fields(wd)}
            tp = wd.find(_T + "TimePeriod")
            if tp is not None:
                r.update(_simple_fields(tp))
            r["WorkingTimes"] = _working_times_text(wd.find(_T + "WorkingTimes"))
            table("CalendarWeekDays").add(r)
        for exc in cal.findall(f"{_T}Exceptions/{_T}Exception"):
            r = {"CalendarUID": uid, **_simple_fields(exc)}
            tp = exc.find(_T + "TimePeriod")
            if tp is not None:
                r.update(_simple_fields(tp))
            r["WorkingTimes"] = _working_times_text(exc.find(_T + "WorkingTimes"))
            table("CalendarExceptions").add(r)
    for res in root.findall(f"{_T}Resources/{_T}Resource"):
        table("Resources").add(_simple_fields(res))
    for asg in root.findall(f"{_T}Assignments/{_T}Assignment"):
        table("Assignments").add(_simple_fields(asg))
    return {name: t.done() for name, t in tables.items()}


# ── Reading ───────────────────────────────────────────────────────────────────

def load(source) -> ET.Element:
    """The document root of an MSPDI file (a path or bytes). Refuses XML that is not
    MSPDI with a message that names what it is, and any document with a DTD (MSPDI
    never has one; a DTD is the only way an XML file can define entities)."""
    data = source if isinstance(source, (bytes, bytearray)) else Path(source).read_bytes()
    if b"<!DOCTYPE" in data[:65536]:
        raise UnsupportedFile("This XML file declares a DTD, which a Microsoft Project XML file never does; it was not read.")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise UnsupportedFile(f"This file is not well-formed XML ({e}).")
    if root.tag != _T + "Project":
        if "APIBusinessObjects" in root.tag:
            raise UnsupportedFile(
                "This is a Primavera P6 XML export, which XERlock does not read. "
                "Export the project from P6 as .xer instead."
            )
        raise UnsupportedFile(
            f"This XML file is not a Microsoft Project XML (MSPDI) file: its root element is "
            f"<{_local(root.tag)}>, not <Project> in the {NS} namespace."
        )
    return root


def read_mspdi(source, source_format: str = "mspdi") -> dict:
    """Read an MSPDI document (path or bytes) into the neutral intermediate
    (analysis.build documents its keys). `source_format` is what the uploaded file was:
    'mspdi' for XML saved by Project, 'mpp' when backend/mpp.py converted it."""
    root = load(source)
    g = _getter(root)
    warnings = []

    minutes_per_day = _int(g("MinutesPerDay"), 480) or 480
    hrs_per_day = minutes_per_day / 60
    hrs_per_week = (_int(g("MinutesPerWeek"), 2400) or 2400) / 60
    default_cal = (g("CalendarUID") or "").strip()
    calendars = read_calendars(root, default_cal, hrs_per_day, hrs_per_week)
    cal_names = {c["clndr_id"]: c["clndr_name"] for c in calendars}
    if default_cal not in cal_names and calendars:
        default_cal = calendars[0]["clndr_id"]
        calendars[0]["default_flag"] = True

    status_date = parse_date(g("StatusDate"))
    if status_date is None:
        warnings.append(
            "This file has no status date (Project > Project Information > Status date), "
            "so the data date is unknown: checks that compare dates with it are not checkable."
        )

    # Resources and assignments: names per task UID. UID 0 is Project's "Unassigned"
    # placeholder and carries no name.
    resource_names = {}
    for res in root.findall(f"{_T}Resources/{_T}Resource"):
        uid, name = (res.findtext(_T + "UID") or "").strip(), (res.findtext(_T + "Name") or "").strip()
        if uid and name:
            resource_names[uid] = name
    task_resources = {}
    for asg in root.findall(f"{_T}Assignments/{_T}Assignment"):
        name = resource_names.get((asg.findtext(_T + "ResourceUID") or "").strip())
        tuid = (asg.findtext(_T + "TaskUID") or "").strip()
        if name and tuid:
            task_resources.setdefault(tuid, set()).add(name)

    # Tasks, in file order. The outline (OutlineLevel) gives the hierarchy: a task's
    # parent is the nearest preceding task one level up. A task with children, or
    # flagged Summary, is a WBS node; the rest are activities.
    tasks = []
    for el in root.findall(f"{_T}Tasks/{_T}Task"):
        t = _getter(el)
        if _flag(t("IsNull")):
            continue
        uid = _int(t("UID"))
        if uid is None:
            continue
        level = _int(t("OutlineLevel"))
        if level is None:
            outline = (t("OutlineNumber") or "").strip()
            level = 0 if uid == 0 else (outline.count(".") + 1 if outline else 1)
        tasks.append({"uid": uid, "el": el, "level": level, "t": t, "children": 0, "parent": None})

    stack = []  # (level, task) of the open ancestors
    for task in tasks:
        while stack and stack[-1][0] >= task["level"]:
            stack.pop()
        if stack:
            task["parent"] = stack[-1][1]
            stack[-1][1]["children"] += 1
        stack.append((task["level"], task))

    name = (g("Title") or "").strip() or (g("Name") or "").strip() or "Project"
    # Inactive tasks (Project 2010+) take no part in the schedule: Project ignores them
    # when scheduling, so they are left out of every population and counted.
    inactive = set()
    for task in tasks:
        if _flag(task["t"]("Active")) is False or (task["parent"] and task["parent"]["uid"] in inactive):
            inactive.add(task["uid"])
    is_summary = {task["uid"]: task["children"] > 0 or _flag(task["t"]("Summary")) is True for task in tasks}

    wbs = []
    has_root = any(task["level"] == 0 for task in tasks)
    if not has_root:
        # Project 98-2003 files and some exports omit the project summary task; the WBS
        # tree still needs one root, so the project itself takes UID 0's place.
        wbs.append({"wbs_id": 0, "wbs_short_name": "0", "wbs_name": name, "parent_wbs_id": None, "seq_num": 0})
    for task in tasks:
        if not is_summary[task["uid"]] or task["uid"] in inactive:
            continue
        parent = task["parent"]
        wbs.append({
            "wbs_id": task["uid"],
            "wbs_short_name": (task["t"]("WBS") or task["t"]("OutlineNumber") or str(task["uid"])).strip(),
            "wbs_name": (task["t"]("Name") or "").strip(),
            "parent_wbs_id": parent["uid"] if parent else (None if task["level"] == 0 else 0),
            "seq_num": _int(task["t"]("ID"), 0) or 0,
        })
    wbs_ids = {w["wbs_id"] for w in wbs}

    def wbs_of(task):
        parent = task["parent"]
        while parent is not None and parent["uid"] not in wbs_ids:
            parent = parent["parent"]
        return parent["uid"] if parent else 0

    by_uid = {task["uid"]: task for task in tasks}
    task_names = {task["uid"]: (task["t"]("Name") or "").strip() for task in tasks}
    activities = []
    links = []
    summary_links = []
    cross_project = 0
    for task in tasks:
        uid, t = task["uid"], task["t"]
        if uid in inactive:
            continue
        duration = iso_duration_hours(t("Duration")) or 0.0
        for link in task["el"].findall(_T + "PredecessorLink"):
            if _flag(link.findtext(_T + "CrossProject")):
                cross_project += 1
                continue
            pred_uid = _int(link.findtext(_T + "PredecessorUID"))
            pred = by_uid.get(pred_uid)
            if pred is None or pred_uid in inactive:
                continue
            fmt = (link.findtext(_T + "LagFormat") or "").strip()
            lag_raw = _int(link.findtext(_T + "LinkLag"), 0) or 0
            pct = lag_raw if fmt in PERCENT_LAG_FORMATS else None
            lag_hrs = (pct / 100 * (iso_duration_hours(pred["t"]("Duration")) or 0.0)) if pct is not None \
                else lag_raw / 600
            rel = {
                "type": LINK_TYPES.get((link.findtext(_T + "Type") or "1").strip(), "PR_FS"),
                "lag_hrs": round(lag_hrs, 4),
                "lag_elapsed": fmt in ELAPSED_LAG_FORMATS,
                "lag_pct": pct,
            }
            if is_summary[uid] or is_summary[pred_uid]:
                summary_links.append({
                    "pred_id": pred_uid, "pred_name": task_names[pred_uid], "pred_is_summary": is_summary[pred_uid],
                    "succ_id": uid, "succ_name": task_names[uid], "succ_is_summary": is_summary[uid],
                    **rel,
                })
            else:
                links.append({"pred_id": pred_uid, "succ_id": uid, **rel})
        if is_summary[uid]:
            continue

        act_start, act_end = parse_date(t("ActualStart")), parse_date(t("ActualFinish"))
        status = "TK_Complete" if act_end else "TK_Active" if act_start else "TK_NotStart"
        cal_uid = (t("CalendarUID") or "").strip()
        if cal_uid not in cal_names:
            cal_uid = default_cal
        cstr_code = (t("ConstraintType") or "0").strip()
        cstr_type = CONSTRAINT_TYPES.get(cstr_code)
        baseline = next((b for b in task["el"].findall(_T + "Baseline")
                         if (b.findtext(_T + "Number") or "0").strip() == "0"), None)
        tf = tenths_of_minutes_hours(t("TotalSlack"))
        activities.append({
            "task_id": uid,
            "task_code": str(uid),
            "task_name": task_names[uid],
            "wbs_id": wbs_of(task),
            "status": status,
            "pct_complete": float(_int(t("PercentComplete"), 0) or 0),
            "pct_complete_type": "CP_Drtn",
            "early_start": parse_date(t("Start")),
            "early_end": parse_date(t("Finish")),
            "late_start": parse_date(t("LateStart")),
            "late_end": parse_date(t("LateFinish")),
            "total_float_hrs": tf,
            "free_float_hrs": tenths_of_minutes_hours(t("FreeSlack")) or 0.0,
            "duration_hrs": duration,
            "remain_duration_hrs": iso_duration_hours(t("RemainingDuration")) or 0.0,
            "task_type": "TT_FinMile" if _flag(t("Milestone")) and duration == 0 else "TT_Task",
            "clndr_id": cal_uid,
            "calendar": cal_names.get(cal_uid, ""),
            "calendar_hrs_per_day": hrs_per_day,
            "driving_path_flag": False,
            "cstr_type": cstr_type,
            "cstr_date": parse_date(t("ConstraintDate")) if cstr_type and cstr_type != "CS_ALAP" else None,
            "cstr_type2": None,
            "cstr_date2": None,
            "act_start": act_start,
            "act_end": act_end,
            "target_start": parse_date(baseline.findtext(_T + "Start")) if baseline is not None else None,
            "target_end": parse_date(baseline.findtext(_T + "Finish")) if baseline is not None else None,
            "activity_codes": [],
            "resource_names": sorted(task_resources.get(str(uid), ())),
            "manual": _flag(t("Manual")) is True,
            "critical": _flag(t("Critical")) is True,
            "deadline": parse_date(t("Deadline")),
        })

    if cross_project:
        warnings.append(f"{cross_project} relationships to tasks in other project files were left out.")
    n_sub = sum(1 for task in tasks if _flag(task["t"]("IsSubproject")))
    if n_sub:
        warnings.append(f"{n_sub} inserted projects (subprojects) appear as summary tasks; their own tasks are only present if the file embeds them.")
    n_ext = sum(1 for task in tasks if _flag(task["t"]("ExternalTask")))
    if n_ext:
        warnings.append(f"{n_ext} external tasks (placeholders for tasks in other project files) are included as activities.")

    critical_limit_days = _int(g("CriticalSlackLimit"), 0) or 0
    options = {
        "present": True,
        "retained_logic": None,
        "progress_override": None,
        "float_type": "",
        # Project counts a lag on the successor's calendar (see METHODOLOGY).
        "lag_calendar": "rcal_Successor",
        "open_ends_critical": None,
        "use_expected_finish": None,
        "float_to_project_finish": None,
        "external_relationships": "",
        "critical_type": "CT_TotFloat",
        "critical_float_hrs": critical_limit_days * hrs_per_day,
    }
    msp_options = {
        "schedule_from_start": _flag(g("ScheduleFromStart")),
        "honor_constraints": _flag(g("HonorConstraints")),
        "minutes_per_day": minutes_per_day,
        "critical_slack_limit_days": critical_limit_days,
        "multiple_critical_paths": _flag(g("MultipleCriticalPaths")),
        "new_tasks_manual": _flag(g("NewTasksAreManual")),
        "splits_in_progress_tasks": _flag(g("SplitsInProgressTasks")),
        "status_date": str(status_date) if status_date else None,
        "current_date": str(parse_date(g("CurrentDate")) or "") or None,
    }

    def recalculate(work_cals, default_cal_obj, longest_path_ids, hrs_per_day_map):
        return recalc.unsupported(RECALC_UNAVAILABLE), None

    return {
        "project": {
            "proj_short_name": name,
            "data_date": str(status_date) if status_date else None,
            "schedule_options": options,
            "source_format": source_format,
            "inactive_activities": sum(1 for u in inactive if not is_summary[u]),
            "summary_links": summary_links,
            "msp_options": msp_options,
        },
        "activities": activities,
        "links": links,
        "wbs": wbs,
        "calendars": calendars,
        "has_resources": len(resource_names) > 0,
        "activity_code_types": [],
        "warnings": warnings,
        "raw_tables": raw_tables(root),
        "ermhdr": {
            "version": (g("SaveVersion") or "").strip(),
            "export_date": (g("LastSaved") or "").strip(),
            "fields": [(g(f) or "").strip() for f in ("SaveVersion", "BuildNumber", "LastSaved", "CreationDate")],
        },
        "recalculate": recalculate,
    }


def parse_mspdi(source, source_format: str = "mspdi") -> dict:
    """Parse an MSPDI document (path or bytes) into the schedule structure the API
    serves (see main.ScheduleData and frontend/src/types/schedule.ts)."""
    return analysis.build(read_mspdi(source, source_format))
