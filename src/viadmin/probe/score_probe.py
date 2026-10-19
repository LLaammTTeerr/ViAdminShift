"""Score the knowledge-cutoff probe and estimate an *effective* cutoff per model.

    uv run python -m viadmin.probe.score_probe --preds results/<run>/predictions.jsonl \
        [--items data/probe/probe_items.jsonl] [--headline data/probe/headline_probe.jsonl] \
        [--condition closed] [--topic non_reform|reform|all] [--json out.json]

Predictions: JSON Lines with at least ``item_id`` and ``raw_output`` (exactly what
``viadmin.eval.runner`` writes, so the probe files can be run with the normal runner and
``--conditions closed``). Optional ``model`` / ``condition`` columns: one report per
(model, condition) group; ``--condition`` keeps only one condition. Rows whose ``item_id``
is not in the item files are ignored; when an item has several rows in a group, the last wins.

Grading reuses ``viadmin.eval.scorer.score`` (MCQ letter extraction / short-answer matching), so
a prediction is ``correct`` only if that scorer labels it so. For short answers with a numeric gold,
Vietnamese/English thousand separators are removed first ("3.321" -> "3321", "10,035" -> "10035"),
because the shared scorer reads "3.321" as the two integers 3 and 321.

Month bins
----------
``anchor`` = every item dated before 2024-09 (2023 facts); then one bin per calendar month
2024-09 .. 2026-03 (the ``month`` field = the month the answer became knowable). By default the
cutoff is estimated on ``non_reform`` items only (generic recency); reform items are reported
per month separately so reform knowledge and general recency are not confounded.

Effective-cutoff rule (threshold T = 2/3, minimum bin size MIN_N = 2)
-------------------------------------------------------------------
A month *passes* if n >= MIN_N and accuracy >= T (with 3-4 items: >= 2 of 3, >= 3 of 4).
Months with n < MIN_N are shown but ignored by the rule.

1. **Estimate (change point).** For every candidate month m that passes, count the
   *disagreements* with a step model "known up to m, unknown afterwards":
   failing months <= m plus passing months > m. The estimate is the passing month with the fewest
   disagreements; ties go to the LATEST such month. This is "the last month with accuracy >= 2/3
   that is followed by a consistent drop": an isolated lucky month after the drop (chance of
   >= 2/3 by guessing among 4 options is ~16% for 3 items) does not move the estimate, but two
   or more later passing months do.
2. **Bracket.** ``lower`` = the month before the first failing month (the model is solid up to
   here); ``upper`` = the last passing month (no evidence of knowledge after it). The estimate
   always lies in [lower, upper] when both exist.
3. **Flags.** ``right_censored`` if the estimate is the last month bin (true cutoff may be later:
   report ">= 2026-03"); ``none_pass`` if no month passes (report "< 2024-09"); ``weak_anchor``
   if anchor accuracy < T -- the model fails even 2023 facts, so a low cutoff is uninformative
   (weak model / poor Vietnamese), not evidence of an early cutoff.

The text plot prints one bar per bin (``#`` = accuracy, ``|`` = the 2/3 threshold) plus the
reform-topic accuracy and the headline-probe labels (correct / outdated / other_wrong / invalid).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

from viadmin.eval.scorer import score

THRESHOLD = Fraction(2, 3)
MIN_N = 2
FIRST_MONTH, LAST_MONTH = "2024-09", "2026-03"
ANCHOR = "anchor"
_SEP_RE = re.compile(r"(?<=\d)[.,](?=\d{3}(?!\d))")


def month_range(first: str = FIRST_MONTH, last: str = LAST_MONTH) -> list[str]:
    y, m = map(int, first.split("-"))
    ly, lm = map(int, last.split("-"))
    out = []
    while (y, m) <= (ly, lm):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def bin_of(item: dict) -> str:
    return ANCHOR if item["month"] < FIRST_MONTH else item["month"]


def read_jsonl(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def strip_thousand_sep(text: str | None) -> str | None:
    if text is None:
        return None
    prev = None
    while prev != text:  # "1.234.567" needs two passes
        prev, text = text, _SEP_RE.sub("", text)
    return text


def grade(item: dict, raw: str | None) -> str:
    """Label of one prediction: correct | outdated | other_wrong | invalid."""
    if item.get("format") != "mcq" and str(item.get("answer", "")).isdigit():
        raw = strip_thousand_sep(raw)
    return score(item, raw).label


def passes(n: int, correct: int) -> bool:
    return n >= MIN_N and Fraction(correct, n) >= THRESHOLD


def estimate_cutoff(bins: dict[str, tuple[int, int]], anchor: tuple[int, int] | None = None,
                    months: list[str] | None = None) -> dict:
    """Apply the documented rule to {month: (n, correct)} (anchor bin excluded)."""
    months = months or month_range()
    usable = [m for m in months if bins.get(m, (0, 0))[0] >= MIN_N]
    status = {m: passes(*bins[m]) for m in usable}
    passing = [m for m in usable if status[m]]
    out: dict = {"estimate": None, "lower": None, "upper": None, "disagreements": None,
                 "right_censored": False, "none_pass": not passing, "weak_anchor": False,
                 "n_usable_months": len(usable)}
    if anchor is not None:
        out["weak_anchor"] = not passes(*anchor) if anchor[0] else True
    if not passing:
        out["summary"] = "< " + months[0] + (" (weak anchors: inconclusive)" if out["weak_anchor"] else "")
        return out
    best, best_err = None, None
    for i, m in enumerate(usable):
        if not status[m]:
            continue
        err = sum(not status[x] for x in usable[: i + 1]) + sum(status[x] for x in usable[i + 1:])
        if best_err is None or err <= best_err:  # ties -> latest
            best, best_err = m, err
    first_fail = next((i for i, m in enumerate(usable) if not status[m]), None)
    out["estimate"], out["disagreements"] = best, best_err
    out["upper"] = passing[-1]
    out["lower"] = None if first_fail == 0 else usable[(first_fail if first_fail is not None else len(usable)) - 1]
    out["right_censored"] = best == usable[-1]
    s = (">= " if out["right_censored"] else "") + best
    s += f" [bracket {out['lower'] or '<' + usable[0]} .. {out['upper']}]"
    if out["weak_anchor"]:
        s += " (weak anchors: treat with caution)"
    out["summary"] = s
    return out


def bar(acc: float | None, width: int = 24) -> str:
    if acc is None:
        return " " * width + " "
    k = round(acc * width)
    t = round(float(THRESHOLD) * width)
    cells = ["#" if i < k else " " for i in range(width)]
    cells.insert(t, "|")
    return "".join(cells)


def score_group(rows: list[dict], items: dict[str, dict], topic: str = "non_reform") -> dict:
    by_item = {r["item_id"]: r for r in rows if r.get("item_id") in items}
    labels = {iid: grade(items[iid], r.get("raw_output")) for iid, r in by_item.items()}
    probe = {iid: lab for iid, lab in labels.items() if items[iid].get("qtype") != "T0_headline"}
    head = {iid: lab for iid, lab in labels.items() if items[iid].get("qtype") == "T0_headline"}

    def tally(pred) -> dict[str, list[int]]:
        t: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for iid, lab in probe.items():
            it = items[iid]
            if pred(it):
                t[bin_of(it)][0] += 1
                t[bin_of(it)][1] += lab == "correct"
        return t

    want = (lambda it: True) if topic == "all" else (lambda it: it["topic"] == topic)
    main = tally(want)
    reform = tally(lambda it: it["topic"] == "reform")
    nonref = tally(lambda it: it["topic"] == "non_reform")
    months = month_range()
    cut = estimate_cutoff({m: tuple(main[m]) for m in months if m in main},
                          anchor=tuple(nonref[ANCHOR]) if ANCHOR in nonref else None, months=months)

    def rows_for(t):
        return {b: {"n": t[b][0], "correct": t[b][1], "accuracy": t[b][1] / t[b][0] if t[b][0] else None}
                for b in [ANCHOR, *months] if b in t}

    n_all = len(probe)
    return {
        "n_probe_scored": n_all,
        "probe_accuracy": sum(lab == "correct" for lab in probe.values()) / n_all if n_all else None,
        "cutoff_topic": topic,
        "by_month": rows_for(main),
        "by_month_reform": rows_for(reform),
        "cutoff": cut,
        "headline": {iid: lab for iid, lab in sorted(head.items())},
        "headline_correct": sum(lab == "correct" for lab in head.values()),
        "headline_outdated": sum(lab == "outdated" for lab in head.values()),
        "missing_items": sorted(i for i in items if i not in by_item),
    }


def text_plot(res: dict, title: str = "") -> str:
    lines = [f"== {title}" if title else "=="]
    lines.append(f"cutoff topic: {res['cutoff_topic']}   probe accuracy (all scored MCQ): "
                 + (f"{res['probe_accuracy']:.2f}" if res["probe_accuracy"] is not None else "n/a")
                 + f"   n={res['n_probe_scored']}")
    lines.append(f"{'bin':8s} {'n':>2s} {'acc':>5s}  {'0':<15s}{'2/3':<9s}{'1'}  reform")
    est = res["cutoff"]["estimate"]
    for b in [ANCHOR, *month_range()]:
        r = res["by_month"].get(b)
        rr = res["by_month_reform"].get(b)
        acc = r["accuracy"] if r else None
        ref = f"{rr['correct']}/{rr['n']}" if rr and rr["n"] else ""
        mark = " <- estimate" if b == est else ""
        n = r["n"] if r else 0
        lines.append(f"{b:8s} {n:2d} {'' if acc is None else f'{acc:5.2f}':>5s}  {bar(acc)}  {ref:6s}{mark}")
    c = res["cutoff"]
    lines.append(f"effective cutoff: {c['summary']}")
    if res["headline"]:
        lines.append(f"headline probe: {res['headline_correct']}/{len(res['headline'])} correct, "
                     f"{res['headline_outdated']} outdated  "
                     + " ".join(f"{k.split('-')[-1]}:{v[0].upper()}" for k, v in res["headline"].items()))
    if res["missing_items"]:
        lines.append(f"({len(res['missing_items'])} items without a prediction)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preds", required=True, help="predictions.jsonl (item_id, raw_output[, model, condition])")
    ap.add_argument("--items", default="data/probe/probe_items.jsonl")
    ap.add_argument("--headline", default="data/probe/headline_probe.jsonl",
                    help="headline short-answer items ('' to skip)")
    ap.add_argument("--condition", default=None, help="keep only this condition (e.g. closed)")
    ap.add_argument("--topic", default="non_reform", choices=["non_reform", "reform", "all"],
                    help="items used for the cutoff estimate (default non_reform)")
    ap.add_argument("--json", default=None, help="write the full result as JSON here")
    a = ap.parse_args(argv)

    items = {it["id"]: it for it in read_jsonl(a.items)}
    if a.headline and Path(a.headline).exists():
        items.update({it["id"]: it for it in read_jsonl(a.headline)})
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in read_jsonl(a.preds):
        if a.condition and r.get("condition", a.condition) != a.condition:
            continue
        groups[(str(r.get("model", "?")), str(r.get("condition", "-")))].append(r)
    if not groups:
        print("no predictions matched", file=sys.stderr)
        return 1
    result = {}
    for (model, cond), rows in sorted(groups.items()):
        res = score_group(rows, items, a.topic)
        result[f"{model}|{cond}"] = res
        print(text_plot(res, f"{model} [{cond}]"))
        print()
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
