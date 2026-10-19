"""Muse-Glimmer chat-template ablation: which system block decides which map the model answers from.

Same server and settings; only the system block differs. Absorbed units, cue=none; strict correct / outdated.
    python3 scripts/analyze_template.py
"""
import collections
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from minitest import label, load  # noqa: E402

G = "results/minitest/gpu"; M = "Muse-Glimmer-30B-Q8_0"
CONDS = [("default: cutoff 2026-01 + today 2026-10-13", ""), ("no date, no cutoff", "-nodate"),
         ("cutoff 2026-01 only", "-cutoffonly"), ("today = 2025-01-01 (pre-reform)", "-date2025")]
QT = [("T6", "T6_province"), ("T1", "T1_ward_province"), ("T1np", "T1np_ward_province")]


def main(out="results/analysis/template"):
    data = {}
    for name, suf in CONDS:
        d = {}
        # Deterministic order; where cue3 and cue3full overlap, cue3full wins (as in analyze_cue.collect).
        for f in sorted(glob.glob(f"{G}/preds_*_items_{M}{suf}.jsonl")):
            full = "cue3full" in os.path.basename(f)
            for p in load(f):
                if full or p["id"] not in d:
                    d[p["id"]] = p
        data[name] = d
    ids = {q: [i for i, p in data[CONDS[3][0]].items() if p["qtype"] == f"{qt}/none" and p.get("absorbed")] for q, qt in QT}
    res = {}
    for name, _ in CONDS:
        res[name] = {}
        for q, _ in QT:
            ps = [data[name][i] for i in ids[q] if i in data[name]]
            c = collections.Counter(label(p) for p in ps)
            res[name][q] = {"n": len(ps), "correct": c["correct"] / len(ps), "outdated": c["outdated"] / len(ps)}
    json.dump(res, open(out + ".json", "w"), indent=1)
    rows = [r"\begin{tabular}{@{}l ccc@{}}", r"\toprule", r"System block & T6 & T1 & T1np \\", r"\midrule"]
    for name, _ in CONDS:
        rows.append(name.replace("_", r"\_") + " & " + " & ".join(
            f"{100 * res[name][q]['correct']:.0f} / {100 * res[name][q]['outdated']:.0f}" for q, _ in QT) + r" \\")
    rows += [r"\bottomrule", r"\end{tabular}"]
    open(out + "_table.tex", "w").write("\n".join(rows) + "\n")
    print("\n".join(rows))


if __name__ == "__main__":
    main()
