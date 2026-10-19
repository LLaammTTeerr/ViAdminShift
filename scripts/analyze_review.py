"""Second-review controls: results/review/preds_<tag>_<model>__<src>.jsonl, tags from review2_controls.sh.

    newname : post-reform ward name, no district. Strata: `renamed-old` = the name also existed before the reform in
              another province (old answer defined); `new-only` = no pre-reform ward of that name elsewhere.
    prefix  : "Hiện nay," (now) and a content-free filler, compared with none/date of the original cue3 / cue3np runs.
    sysasof : "answer as of 10/2026" in the system prompt, on the sysdate items (compare sysprompt.json).
    r2, r3  : repeats of the cue3 ladder; run-to-run spread of T1 absorbed accuracy per cue and item-level agreement.

    python3 scripts/analyze_review.py
"""
import collections
import glob
import json
import os
import sys

sys.path.insert(0, "scripts")
from analyze_cue import label2, boot_delta  # noqa: E402

R = "results/review"
ORIG = {"api": "results/minitest/api", "claude": "results/minitest/claude", "claude_nothink": "results/minitest/claude_nothink",
        "claude_none": "results/minitest/claude_none"}


def load(p):
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


def rate(ps, lab="correct"):
    return round(sum(label2(p) == lab for p in ps) / len(ps), 3) if ps else None


def original(model, src, kind):
    """The model's first cue3 / cue3np run (same layout analyze_cue reads)."""
    out = {}
    for f in sorted(glob.glob(f"results/minitest/{src}/preds_{kind}*_*.jsonl")):
        if kind == "cue3" and "cue3np" in f:
            continue
        for p in load(f):
            if p.get("model") == model:
                out.setdefault(p["id"], p)  # cue3 / cue3sub / cue3full overlap: one prediction per item
    return list(out.values())


def main():
    res = {}
    for f in sorted(glob.glob(f"{R}/preds_*__*.jsonl")):
        tag, rest = os.path.basename(f)[6:-6].split("_", 1)
        model, src = rest.rsplit("__", 1)
        r = res.setdefault(f"{model}|{src}", {})
        ps = load(f)
        if tag == "newname":
            for name, keep in (("renamed-old", lambda p: bool(p["old"])), ("new-only", lambda p: not p["old"])):
                sub = [p for p in ps if keep(p)]
                cell = {}
                by = collections.defaultdict(dict)
                for cue in ("none", "date", "reform"):
                    pc = [p for p in sub if p["cue"] == cue]
                    cell[cue] = {"n": len(pc), "acc": rate(pc), "outdated": rate(pc, "outdated") if name == "renamed-old" else None,
                                 "both_new": rate(pc, "both_new"), "both_old": rate(pc, "both_old"),
                                 "new_first": round((rate(pc) or 0) + (rate(pc, "both_new") or 0), 3) if pc else None}
                    for p in pc:
                        by[p["base"]][cue] = float(label2(p) == "correct")
                d = boot_delta(by, "date", "none")
                cell["d_date"] = dict(zip(("delta", "lo", "hi", "n"), d)) if d else None
                r[f"newname {name}"] = cell
        elif tag == "prefix":
            for st, kind, qt in (("T1", "cue3", "T1_ward"), ("T1np", "cue3np", "T1np_ward")):
                orig = [p for p in original(model, src, kind) if p["qtype"].startswith(qt) and p.get("absorbed")]
                new = [p for p in ps if p["qtype"].startswith(qt) and p.get("absorbed")]
                bases = {p["base"] for p in new}
                cell = {}
                for cue in ("none", "date"):
                    pc = [p for p in orig if p["cue"] == cue and p["base"] in bases]
                    cell[cue] = {"n": len(pc), "acc": rate(pc), "outdated": rate(pc, "outdated"),
                                 "new_first": round((rate(pc) or 0) + (rate(pc, "both_new") or 0), 3) if pc else None}
                for cue in ("now", "filler"):
                    pc = [p for p in new if p["cue"] == cue]
                    cell[cue] = {"n": len(pc), "acc": rate(pc), "outdated": rate(pc, "outdated"),
                                 "new_first": round((rate(pc) or 0) + (rate(pc, "both_new") or 0), 3) if pc else None}
                r[f"prefix {st} absorbed"] = cell
        elif tag == "sysasof":
            for st, qt in (("T1", "T1_ward"), ("T1np", "T1np_ward"), ("T6", "T6")):
                pc = [p for p in ps if p["qtype"].startswith(qt) and p.get("absorbed")]
                r[f"sysasof {st} absorbed"] = {"n": len(pc), "acc": rate(pc), "outdated": rate(pc, "outdated")}
        elif tag in ("r2", "r3"):
            for cue in ("none", "date", "reform"):
                pc = [p for p in ps if p["qtype"].startswith("T1_ward") and p.get("absorbed") and p["cue"] == cue]
                r.setdefault("repeat T1 absorbed", {}).setdefault(cue, {})[tag] = rate(pc)
    # repeat: add the original run and item-level agreement across the three runs
    for key, r in res.items():
        if "repeat T1 absorbed" not in r:
            continue
        model, src = key.split("|")
        runs = {"r1": [p for p in original(model, src, "cue3") if p["qtype"].startswith("T1_ward") and p.get("absorbed")]}
        for tag in ("r2", "r3"):
            runs[tag] = [p for p in load(f"{R}/preds_{tag}_{model}__{src}.jsonl") if p["qtype"].startswith("T1_ward") and p.get("absorbed")]
        ids = set.intersection(*[{p["id"] for p in v} for v in runs.values()])
        lab = {t: {p["id"]: label2(p) for p in v if p["id"] in ids} for t, v in runs.items()}
        for cue in ("none", "date", "reform"):
            c = r["repeat T1 absorbed"][cue]
            c["r1"] = rate([p for p in runs["r1"] if p["cue"] == cue and p["id"] in ids])
            idc = [i for i in ids if i.endswith("__" + cue)]
            c["agree3"] = round(sum(len({lab[t][i] for t in lab}) == 1 for i in idc) / len(idc), 3) if idc else None
            c["n"] = len(idc)
    json.dump(res, open("results/analysis/review.json", "w"), indent=1, ensure_ascii=False)
    for k, r in res.items():
        print(k)
        for s, c in r.items():
            print("   ", s, json.dumps(c, ensure_ascii=False))


if __name__ == "__main__":
    main()


LAB = [("deepseek-flash|api", "DeepSeek-V4.1-Flash"), ("claude-haiku-5-5|claude", "Claude Haiku 5.5"),
       ("claude-sonnet-5-5|claude_nothink", "Claude Sonnet 5.5"), ("claude-opus-5-5|claude", "Claude Opus 5.5"),
       ("claude-fable-5-1|claude_none", "Claude Fable 5.1"), ("Muse-Glimmer-30B-Q8_0-nodate|gpu", "Muse-Glimmer-30B$^\\dagger$")]


def tex(path="results/analysis/review.json", out="results/analysis/frame_table.tex", short=False):
    """Frame control (post-reform ward name, no district) and prefix control (T1np), cue none unless stated.
    all cells new-first / old-only (%), except the new-only column (new-first)."""
    d = json.load(open(path))
    f = lambda x: "--" if x is None else f"{100 * x:.0f}"
    rows = [r"\begin{tabular}{@{}l ccc cccc@{}}", r"\toprule",
            r" & \multicolumn{3}{c}{post-reform name} & \multicolumn{4}{c}{T1np (ward, district)} \\",
            r"\cmidrule(lr){2-4}\cmidrule(lr){5-8}",
            r" & \multicolumn{2}{c}{also pre-reform} & new only & & & ``hiện & \\",
            r"Model & none & date & none & none & date & nay'' & filler \\", r"\midrule"]
    for k, lab in LAB:
        r = d.get(k)
        if not r:
            continue
        if short:
            lab = lab.replace("Claude ", "").replace(" (no think)", "$^-$").replace("-V4.1-Flash", "").replace("-30B", "")
        a, b, p = r["newname renamed-old"], r["newname new-only"], r["prefix T1np absorbed"]
        rows.append(f"{lab} & {f(a['none']['new_first'])}/{f(a['none']['outdated'])} & {f(a['date']['new_first'])}/{f(a['date']['outdated'])} & "
                    f"{f(b['none']['new_first'])} & " + " & ".join(f"{f(p[c]['new_first'])}/{f(p[c]['outdated'])}" for c in ("none", "date", "now", "filler")) + r" \\")
    rows += [r"\bottomrule", r"\end{tabular}"]
    open(out, "w").write("\n".join(rows) + "\n")


if __name__ == "__main__":
    tex()
    tex(out="results/analysis/frame_table_short.tex", short=True)
