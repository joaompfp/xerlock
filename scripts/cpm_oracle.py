#!/usr/bin/env python3
"""
Oracle harness for the CPM engine: parse each given .xer exactly as the app does and
print how well the recalculation reproduces P6's stored dates and float.

Not part of CI. The files it is run on are client-confidential, so it prints
aggregate counts only, identifies files by position (1..N), never by name or path,
and never prints an activity code, name, date or any other content.

    .venv/bin/python scripts/cpm_oracle.py /path/to/*.xer
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.main import parse_xer  # noqa: E402


def main(paths):
    if not paths:
        print(__doc__)
        return 2
    fields = ("es", "ef", "ls", "lf", "tf", "ff")
    print(f"{'file':>4} {'acts':>5} {'cmp':>5} {'diff':>5} " + " ".join(f"{f:>4}" for f in fields) + "  status")
    worst = 0
    for i, path in enumerate(paths, 1):
        data = parse_xer(path)
        r = data.project.recalculation or {}
        cpt = data.project.critical_path_test
        by_field = r.get("by_field", {})
        if not r.get("supported"):
            status = f"refused: {_category(r.get('reason'))}"
        elif r.get("differing"):
            status = "differs"
            worst = max(worst, r["differing"])
        else:
            status = "match"
            if cpt:
                status += f"; CPT {'pass' if cpt['passed'] else 'FAIL'} ({cpt['finish_delta_hrs']}/{cpt['expected_delta_hrs']} h)"
        print(f"{i:>4} {data.project.total_activities:>5} {r.get('compared', 0):>5} {r.get('differing', 0):>5} "
              + " ".join(f"{by_field.get(f, 0):>4}" for f in fields) + f"  {status}")
        if r.get("differing"):
            # Aggregate shape of the mismatches: which field, and the delta distribution.
            deltas = Counter((d["field"], _bucket(d["delta_hrs"])) for d in r["differences"])
            print("       deltas:", ", ".join(f"{f}:{b}x{n}" for (f, b), n in sorted(deltas.items())))
    return 1 if worst else 0


def _category(reason):
    """The refusal reason without any file content (reasons contain only counts)."""
    return reason or "unknown"


def _bucket(delta):
    if delta is None:
        return "missing"
    return f"{delta:+g}h"


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
