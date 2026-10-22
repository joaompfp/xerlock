"""
Working-time arithmetic on P6 calendars.

P6 measures every duration, lag and float in *working* hours of a calendar, never in
elapsed clock time. A finish-to-start link from Friday 16:00 to Monday 08:00 on a
5-day calendar has zero free float, though 64 clock hours separate the two dates.
Any test of "is this relationship driving?" or "how long is the remaining critical
path?" has to be measured in the same units P6 used, or it is measuring weekends.

Calendars come from ``parse_calendar_data`` in ``xer``: weekday keys "1".."7" are
Sunday..Saturday, each a list of {"start": "HH:MM", "finish": "HH:MM"} periods; dated
exceptions replace the weekday pattern for that date (no periods = non-working).
"""

from datetime import date, datetime, timedelta

# Spans are bounded so a corrupt date (year 2999, a common P6 placeholder) cannot
# stall a parse or build a running total centuries long.
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
        # (first day ordinal, running totals): replaced whole, never edited in place, so
        # a calendar shared between requests is never read half-rebuilt.
        self._table: tuple[int, list[int]] = (0, [])

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

    # ── Whole days in bulk ────────────────────────────────────────────────────
    # A schedule asks these two questions tens of thousands of times over spans of
    # months, so whole days are not walked one at a time: in the table (base, cum),
    # cum[i] holds the working minutes of every day from `base` up to (not including)
    # day `base + i`, built on demand. Only the first and last day of a span are
    # looked at period by period.

    def _day_minutes(self, d: date) -> int:
        return sum(f - s for s, f in self.spans_on(d))

    def _cover(self, lo: int, hi: int):
        """Running totals covering day ordinals lo..hi inclusive, as a function giving
        the working minutes before a day (measured from the table's own start)."""
        base, cum = self._table
        if not (cum and base <= lo and hi < base + len(cum) - 1):
            if cum:
                lo, hi = min(lo, base), max(hi, base + len(cum) - 2)
            lo, hi = lo - 366, hi + 366
            cum, total = [0], 0
            for o in range(lo, hi + 1):
                total += self._day_minutes(date.fromordinal(o))
                cum.append(total)
            base = lo
            self._table = (base, cum)
        return lambda o: cum[o - base]

    def _whole_days(self, first: int, last: int) -> int:
        """Working minutes in days first..last inclusive (0 when last < first)."""
        if last < first:
            return 0
        before = self._cover(first, last)
        return before(last + 1) - before(first)

    def _on_day(self, d: date, lo: float, hi: float) -> float:
        return sum(max(0, min(f, hi) - max(s, lo)) for s, f in self.spans_on(d))

    def working_hours_between(self, t0: datetime, t1: datetime) -> float:
        """Working hours from t0 to t1; negative when t1 precedes t0."""
        if t1 < t0:
            return -self.working_hours_between(t1, t0)
        d0, d1 = t0.date(), t1.date()
        if (d1 - d0).days >= MAX_SPAN_DAYS:
            d1 = d0 + timedelta(days=MAX_SPAN_DAYS - 1)
            t1 = datetime.combine(d1, datetime.max.time())
        m0 = (t0 - datetime.combine(d0, datetime.min.time())).total_seconds() / 60
        m1 = (t1 - datetime.combine(d1, datetime.min.time())).total_seconds() / 60
        if d0 == d1:
            return self._on_day(d0, m0, m1) / 60
        total = self._on_day(d0, m0, 1440) + self._on_day(d1, 0, m1)
        total += self._whole_days(d0.toordinal() + 1, d1.toordinal() - 1)
        return total / 60

    def add_working_hours(self, t: datetime, hours: float) -> datetime:
        """The instant `hours` working hours after t (before it, when negative)."""
        if hours == 0:
            return t
        remaining = abs(hours) * 60
        forward = hours > 0
        d = t.date()
        here = (t - datetime.combine(d, datetime.min.time())).total_seconds() / 60
        # The rest of t's own day first.
        found, remaining = self._within_day(d, here, remaining, forward)
        if found is not None:
            return found
        # Then the day the hours run out on, found by bisecting the running totals.
        o = d.toordinal()
        step = 1 if forward else -1
        limit = o + step * MAX_SPAN_DAYS
        before = self._cover(min(o, limit), max(o, limit))
        first = o + step
        if forward:
            # The first day D with minutes(first..D) >= remaining.
            start = before(first)
            lo, hi = first, limit
            if before(hi + 1) - start < remaining:
                return t
            while lo < hi:
                mid = (lo + hi) // 2
                if before(mid + 1) - start >= remaining:
                    hi = mid
                else:
                    lo = mid + 1
            remaining -= before(lo) - start
        else:
            # The last day D with minutes(D..first) >= remaining.
            end = before(first + 1)
            lo, hi = limit, first
            if end - before(lo) < remaining:
                return t
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if end - before(mid) >= remaining:
                    lo = mid
                else:
                    hi = mid - 1
            remaining -= end - before(lo + 1)
        found, _ = self._within_day(date.fromordinal(lo), 0 if forward else 1440, remaining, forward)
        return found if found is not None else t

    def _within_day(self, d: date, here: float, remaining: float, forward: bool):
        """Walks d's periods from minute `here` (forwards or back). Returns the instant
        the hours run out, or None with what is left once the day is spent."""
        day0 = datetime.combine(d, datetime.min.time())
        spans = self.spans_on(d)
        for s, f in (spans if forward else reversed(spans)):
            if forward:
                s = max(s, here)
                if s >= f:
                    continue
                if f - s >= remaining:
                    return day0 + timedelta(minutes=s + remaining), 0
            else:
                f = min(f, here)
                if f <= s:
                    continue
                if f - s >= remaining:
                    return day0 + timedelta(minutes=f - remaining), 0
            remaining -= f - s
        return None, remaining

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
