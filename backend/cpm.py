"""
Scheduling rules shared by the driving-relationship check and the CPM engine.

Everything here is a pure function over plain data: no FastAPI, no PyP6XER. The
rules reproduce Primavera P6's behaviour, and each one says which P6 setting or
convention it follows so a reviewer can check it against the file.
"""

from backend.worktime import ALL_HOURS, WorkCalendar


def lag_calendar(basis: str, pred_cal: WorkCalendar, succ_cal: WorkCalendar,
                 default_cal) -> WorkCalendar:
    """The calendar a relationship lag is measured on, per
    SCHEDOPTIONS.sched_calendar_on_relationship_lag. P6's default is the
    predecessor's calendar, which is also what an export without the table gets."""
    if basis == "rcal_Successor":
        return succ_cal
    if basis == "rcal_24Hour":
        return ALL_HOURS
    if basis == "rcal_ProjDefault":
        return default_cal or pred_cal
    return pred_cal
