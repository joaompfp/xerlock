#!/usr/bin/env python3
"""
Corpus report for the Microsoft Project readers: parse every .mpp and .xml under the
given directories exactly as the app does and print aggregates only.

    scripts/fetch_msp_corpus.sh                       # MPXJ test data -> .corpus/mpxj
    .venv/bin/python scripts/msp_corpus.py .corpus/mpxj [more dirs...]

Not part of CI (it needs Java for the .mpp files and takes minutes). Prints, per
directory: files parsed / refused by reason, activity and link counts, and for every
.mpp that has an MSPDI twin (same stem, saved by the same Project version) whether the
two paths agree on dates, float, flags and links, with the fields that differ; and the
recalculation's result per file (refused with its reason, differs, or match with the
Critical Path Test's verdict). Files are identified by their basename only; nothing
from inside them is printed, so it is safe on confidential files too.
"""

import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.schedule import parse_schedule  # noqa: E402

COMPARED = ("early_start", "early_end", "late_start", "late_end", "total_float_hrs",
            "free_float_hrs", "is_critical", "is_longest_path", "status", "task_type",
            "cstr_type", "cstr_date", "act_start", "act_end", "duration_hrs", "manual")


def core(data):
    """What the two paths must agree on, keyed by task UID."""
    out = {}
    for a in data["activities"]:
        out[a["task_id"]] = {f: a[f] for f in COMPARED}
        out[a["task_id"]]["links"] = sorted((p["task_id"], p["type"], p["lag_hrs"], p["driving"]) for p in a["predecessors"])
    return out


def twin_of(mpp: Path):
    """The MSPDI file saved alongside: generated/<x>/<name>-projectNNNN-mpp14.mpp has
    <name>-projectNNNN-mspdi.xml; top-level foo.mpp may have foo.xml."""
    stem = mpp.stem
    for i in ("mpp8", "mpp9", "mpp12", "mpp14"):
        if stem.endswith("-" + i):
            cand = mpp.with_name(stem[: -len(i)] + "mspdi.xml")
            return cand if cand.exists() else None
    cand = mpp.with_suffix(".xml")
    return cand if cand.exists() else None


def reason_category(reason) -> str:
    """A refusal reason without its counts, so like reasons group together."""
    import re
    return re.sub(r"^\d+ ", "", reason or "unknown")


def refusal_category(msg: str) -> str:
    for key in ("password", "Primavera", "not well-formed", "DTD", "not a Microsoft Project XML",
                "did not recognise", "not a P6", "MPXJ could not read"):
        if key in msg:
            return key
    return "other"


def main(dirs):
    if not dirs:
        print(__doc__)
        return 2
    totals = Counter()
    for d in dirs:
        files = sorted(p for p in Path(d).rglob("*") if p.suffix.lower() in (".mpp", ".xml"))
        parsed = {}
        refused = Counter()
        crashed = Counter()
        counts = Counter()
        refusals = Counter()
        differing = []
        for p in files:
            try:
                data = parse_schedule(str(p))
            except ValueError as e:
                refused[(p.suffix.lower(), refusal_category(str(e)))] += 1
                continue
            except Exception as e:  # a crash is a defect: name the type, never the content
                crashed[(p.suffix.lower(), type(e).__name__)] += 1
                continue
            parsed[p] = data
            kind = data["project"].get("source_format", "?")
            counts[kind + " files"] += 1
            counts[kind + " activities"] += data["project"]["total_activities"]
            counts[kind + " links"] += sum(len(a["predecessors"]) for a in data["activities"])
            counts[kind + " with data date"] += bool(data["project"]["data_date"])
            counts[kind + " inactive"] += data["project"].get("inactive_activities", 0)
            counts[kind + " summary links"] += len(data["project"].get("summary_links", []))
            counts[kind + " manual"] += sum(1 for a in data["activities"] if a.get("manual"))
            counts[kind + " elapsed/pct lags"] += sum(1 for a in data["activities"] for l in a["predecessors"]
                                                    if l.get("lag_elapsed") or l.get("lag_pct") is not None)
            # The recalculation (backend/recalc_msp.py): refused with a reason, or compared
            # with Project's stored values; the CPT runs only on an exact match.
            r = data["project"].get("recalculation") or {}
            cpt = data["project"].get("critical_path_test")
            if not r.get("supported"):
                refusals[(kind, reason_category(r.get("reason")))] += 1
            elif r.get("differing"):
                counts[kind + " recalc: differs"] += 1
                differing.append((p.name, r["differing"], r["compared"], {f: n for f, n in r["by_field"].items() if n}))
            else:
                counts[kind + " recalc: match"] += 1
                counts[kind + " recalc: match with logic"] += bool(any(a["predecessors"] for a in data["activities"]))
                if cpt:
                    counts[kind + " recalc: CPT " + ("pass" if cpt["passed"] else "FAIL")] += 1
                elif r.get("uncovered"):
                    counts[kind + " recalc: CPT withheld (uncovered)"] += 1
        print(f"== {d}: {len(files)} files")
        for k, v in sorted(counts.items()):
            print(f"   {k:32} {v}")
        for (ext, why), n in sorted(refused.items()):
            print(f"   refused {ext} ({why}): {n}")
        for (ext, why), n in sorted(crashed.items()):
            print(f"   CRASH {ext} ({why}): {n}")
        for (kind, why), n in sorted(refusals.items()):
            print(f"   {kind} recalc refused ({why}): {n}")
        for name, n, cmp, fields in differing:
            print(f"   recalc differs: {name}: {n} of {cmp} tasks, fields {fields}")

        # .mpp vs .xml twins
        agree = differ = 0
        fields = Counter()
        for p, data in parsed.items():
            if p.suffix.lower() != ".mpp":
                continue
            twin = twin_of(p)
            if twin is None or twin not in parsed:
                continue
            a, b = core(data), core(parsed[twin])
            if a == b:
                agree += 1
                continue
            differ += 1
            if set(a) != set(b):
                fields["task set"] += 1
            for tid in set(a) & set(b):
                for f in list(COMPARED) + ["links"]:
                    if a[tid][f] != b[tid][f]:
                        fields[f] += 1
        print(f"   twins: {agree} agree, {differ} differ" + (
            " — differing fields (task-field counts): " + ", ".join(f"{f} {n}" for f, n in fields.most_common()) if differ else ""))
        totals["parsed"] += len(parsed)
        totals["refused"] += sum(refused.values())
        totals["crashed"] += sum(crashed.values())
    print(f"== total: {totals['parsed']} parsed, {totals['refused']} refused, {totals['crashed']} crashed")
    return 1 if totals["crashed"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
