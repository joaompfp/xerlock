"""
Working-time arithmetic on P6 calendars.

P6 measures every duration, lag and float in *working* hours of a calendar, never in
elapsed clock time. A finish-to-start link from Friday 16:00 to Monday 08:00 on a
5-day calendar has zero free float, though 64 clock hours separate the two dates.
Any test of "is this relationship driving?" or "how long is the remaining critical
path?" has to be measured in the same units P6 used, or it is measuring weekends.

Calendars come from ``parse_calendar_data`` in ``main``: weekday keys "1".."7" are
Sunday..Saturday, each a list of {"start": "HH:MM", "finish": "HH:MM"} periods; dated
exceptions replace the weekday pattern for that date (no periods = non-working).
"""

from datetime import date, datetime, timedelta

# Walking a calendar day by day is linear in the span. Bounded so a corrupt date
# (year 2999, a common P6 placeholder) cannot stall a parse.
MAX_SPAN_DAYS = 366 * 30


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


class WorkCalendar:
    def __init__(self, weekdays: dict, exceptions: list):
        # P6 weekday 1=Sunday; Python weekday() 0=Monday. Index by Python weekday.
        self._week = [[] for _ in range(7)]
        for p6_day, periods in weekdays.items():
            self._week[(int(p6_day) + 5) % 7] = self._spans(periods)
        self._exceptions = {
            date.fromisoformat(e["date"]): self._spans(e["periods"]) for e in exceptions
        }

    @staticmethod
    def _spans(periods):
        """(start_min, finish_min) per period. A finish at or before the start ends at
        midnight: P6 writes a 24-hour day as 00:00-00:00."""
        out = []
        for p in periods:
            s, f = _minutes(p["start"]), _minutes(p["finish"])
            out.append((s, f if f > s else 1440))
        return sorted(out)

    def spans_on(self, d: date):
        if d in self._exceptions:
            return self._exceptions[d]
        return self._week[d.weekday()]

    def working_hours_between(self, t0: datetime, t1: datetime) -> float:
        """Working hours from t0 to t1; negative when t1 precedes t0."""
        if t1 < t0:
            return -self.working_hours_between(t1, t0)
        total = 0
        d = t0.date()
        for _ in range(MAX_SPAN_DAYS):
            if d > t1.date():
                break
            day0 = datetime.combine(d, datetime.min.time())
            lo = (t0 - day0).total_seconds() / 60 if d == t0.date() else 0
            hi = (t1 - day0).total_seconds() / 60 if d == t1.date() else 1440
            for s, f in self.spans_on(d):
                total += max(0, min(f, hi) - max(s, lo))
            d += timedelta(days=1)
        return total / 60

    def add_working_hours(self, t: datetime, hours: float) -> datetime:
        """The instant `hours` working hours after t (before it, when negative)."""
        if hours == 0:
            return t
        remaining = abs(hours) * 60
        forward = hours > 0
        d = t.date()
        for _ in range(MAX_SPAN_DAYS):
            day0 = datetime.combine(d, datetime.min.time())
            here = (t - day0).total_seconds() / 60 if d == t.date() else (0 if forward else 1440)
            spans = self.spans_on(d)
            for s, f in (spans if forward else reversed(spans)):
                if forward:
                    s = max(s, here)
                    if s >= f:
                        continue
                    if f - s >= remaining:
                        return day0 + timedelta(minutes=s + remaining)
                else:
                    f = min(f, here)
                    if f <= s:
                        continue
                    if f - s >= remaining:
                        return day0 + timedelta(minutes=f - remaining)
                remaining -= f - s
            d += timedelta(days=1 if forward else -1)
        return t

    # P6 never schedules into non-working time. A start that logic puts at Friday
    # 16:00 (a period's end) becomes Monday 08:00; a finish may sit exactly on a
    # period's end, and when logic puts it in non-working time the forward pass moves
    # it on to the next working start. The backward pass mirrors this: a late finish
    # at Monday 08:00 (a period's start) becomes Friday 16:00.

    def next_work_start(self, t: datetime) -> datetime:
        """t if work is under way at t (period start inclusive, end exclusive), else
        the next period start."""
        return self._snap(t, forward=True, inclusive=False)

    def next_work_finish(self, t: datetime) -> datetime:
        """t if it lies in a period including its end, else the next period start."""
        return self._snap(t, forward=True, inclusive=True)

    def prev_work_finish(self, t: datetime) -> datetime:
        """t if work has been done at t (period start exclusive, end inclusive), else
        the previous period end."""
        return self._snap(t, forward=False, inclusive=False)

    def prev_work_start(self, t: datetime) -> datetime:
        """t if it lies in a period including its start, else the previous period end."""
        return self._snap(t, forward=False, inclusive=True)

    def _snap(self, t: datetime, forward: bool, inclusive: bool) -> datetime:
        d = t.date()
        for _ in range(MAX_SPAN_DAYS):
            day0 = datetime.combine(d, datetime.min.time())
            m = (t - day0).total_seconds() / 60  # minutes into day d; outside 0..1440 on other days
            spans = self.spans_on(d)
            if forward:
                for s, f in spans:
                    if s <= m < f or (inclusive and m == f):
                        return t
                    if s > m:
                        return day0 + timedelta(minutes=s)
                d += timedelta(days=1)
            else:
                for s, f in reversed(spans):
                    if s < m <= f or (inclusive and m == s):
                        return t
                    if f < m:
                        return day0 + timedelta(minutes=f)
                d -= timedelta(days=1)
        return t


# P6's "24 Hour" calendar: every minute of every day is working time.
ALL_HOURS = WorkCalendar({str(d): [{"start": "00:00", "finish": "00:00"}] for d in range(1, 8)}, [])
