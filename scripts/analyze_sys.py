"""System-prompt date experiment: does 'Hôm nay là ngày 13/10/2026.' in the SYSTEM prompt fix the temporal default?

Compares, on the same cue=none questions (T6 + T1 + T1np, absorbed units):
  sys0   plain assistant system prompt            results/minitest/sysprompt/preds_sys0_<model>__<src>.jsonl
  sys1   same + today's date                      results/minitest/sysprompt/preds_sys1_<model>__<src>.jsonl
  none   no system prompt, no cue (cue3 runs)     results/minitest/<src>/preds_cue3*_<model>.jsonl
  date   no system prompt, date in the question   (cue3 runs, cue=date)
Strict accuracy (pre-registered label); paired bootstrap CI for sys1 - sys0. Old-only (label 'outdated') paired
deltas with bootstrap CIs (analyze_cue.boot_delta, B=2000, seed 0) for the date conditions against sys1
('old_only_vs_sys1') and for reasoning on minus reasoning off of the same model ('old_only_think_vs_off', on the
*_think rows).

    python3 scripts/analyze_sys.py
"""
import collections
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from analyze_cue import SRC_ALIAS, boot_delta, collect, hidden, label2  # noqa: E402
from minitest import label, load  # noqa: E402

STRATA = [("T6 absorbed", "T6_province"), ("T1 absorbed", "T1_ward_province"), ("T1np absorbed", "T1np_ward_province")]


def acc(ps):
    return sum(label(p) == "correct" for p in ps) / len(ps) if ps else None


def three(ps):
    """new-first (correct or both, new named first) / old-first-then-new / old-only, as fractions."""
    if not ps:
        return None
    c = collections.Counter(label2(p) for p in ps)
    n = len(ps)
    return {"new_first": (c["correct"] + c["both_new"]) / n, "both_old": c["both_old"] / n, "old_only": c["outdated"] / n}


def main(root="results/minitest", out="results/analysis/sysprompt"):
    cue = collect(root)
    rows, olds = {}, {}
    for f in sorted(glob.glob(f"{root}/sysprompt/preds_sys0_*.jsonl")):
        model, src = re.match(r".*/preds_sys0_(.+)__(.+)\.jsonl", f).groups()
        f1 = f.replace("preds_sys0_", "preds_sys1_")
        if not os.path.exists(f1):
            continue
        s0 = {p["id"]: p for p in load(f)}
        s1 = {p["id"]: p for p in load(f1)}
        fq = f.replace("preds_sys0_", "preds_sys0q_")  # sys0 + date IN THE QUESTION (confound control)
        sq = {p["base"]: p for p in load(fq)} if os.path.exists(fq) else {}
        c = cue.get((model, SRC_ALIAS.get(src, src)), {})
        r = {}
        for name, qt in STRATA:
            def sel(d, cueval="none"):
                return [p for p in d.values() if p["qtype"] == f"{qt}/{cueval}" and p.get("absorbed")]
            a0, a1 = sel(s0), sel(s1)
            if not a0:
                continue
            by = collections.defaultdict(dict)
            for p in a0:
                by[p["base"]]["sys0"] = float(label(p) == "correct")
            for p in a1:
                by[p["base"]]["sys1"] = float(label(p) == "correct")
            d = boot_delta(by, "sys1", "sys0")
            bases = {p["base"] for p in a0}  # same units as the system-prompt runs
            same = lambda ps: [p for p in ps if p["base"] in bases]
            aq = [sq[b] for b in bases if b in sq and sq[b]["qtype"] == f"{qt}/date"]
            for p in aq:
                by[p["base"]]["sys0q"] = float(label(p) == "correct")
            dq = boot_delta(by, "sys0q", "sys1")
            extra = {"three": {"sys0": three(a0), "sys1": three(a1), "sys0q": three(aq)},
                     "reasoning": sum(hidden(p) for p in a1) / len(a1) if a1 else None}
            for tag, cueval in (("sys0qm", "date"), ("sys2025", "none"), ("q2025", "date")):  # reviewer controls
                ft = f.replace("preds_sys0_", f"preds_{tag}_")
                if not os.path.exists(ft):
                    continue
                pt = [p for p in load(ft) if p["qtype"] == f"{qt}/{cueval}" and p.get("absorbed") and p["base"] in bases]
                extra[tag] = acc(pt)
                extra["three"][tag] = three(pt)
                extra[tag + "_outdated"] = sum(label(p) == "outdated" for p in pt) / len(pt) if pt else None
                for p in pt:
                    by[p["base"]][tag] = float(label(p) == "correct")
            dm = boot_delta(by, "sys0qm", "sys1") if "sys0qm" in extra else None
            extra["d_qm_vs_sys"] = dict(zip(("delta", "lo", "hi", "n"), dm)) if dm else None
            extra["sys0_outdated"] = sum(label(p) == "outdated" for p in a0) / len(a0)
            fa = f"results/review/preds_sysasof_{model}__{src}.jsonl"
            pa = []
            if os.path.exists(fa):
                pa = [p for p in load(fa) if p["qtype"] == f"{qt}/none" and p.get("absorbed") and p["base"] in bases]
                extra["three"]["sysasof"] = three(pa)
            old = collections.defaultdict(dict)  # base -> condition -> 1 if the answer names only the old unit
            for tag, ps in (("sys1", a1), ("sys0q", aq), ("sysasof", pa)):
                for p in ps:
                    old[p["base"]][tag] = float(label(p) == "outdated")
            ft = f.replace("preds_sys0_", "preds_sys0qm_")
            if os.path.exists(ft):
                for p in load(ft):
                    if p["qtype"] == f"{qt}/date" and p.get("absorbed") and p["base"] in bases:
                        old[p["base"]]["sys0qm"] = float(label(p) == "outdated")
            olds[(model, src, name)] = old
            extra["old_only_vs_sys1"] = {}
            for tag in ("sys0q", "sys0qm", "sysasof"):
                dd = boot_delta(old, tag, "sys1")
                if dd:
                    extra["old_only_vs_sys1"][tag] = dict(zip(("delta", "lo", "hi", "n"), dd))
            r[name] = {**extra, "sys0q": acc(aq), "d_q_vs_sys": dict(zip(("delta", "lo", "hi", "n"), dq)) if dq else None,
                       "n": len(a0), "sys0": acc(a0), "sys1": acc(a1), "none": acc(same(sel(c))), "date_in_q": acc(same(sel(c, "date"))),
                       "d_sys": dict(zip(("delta", "lo", "hi", "n"), d)) if d else None}
        rows[f"{model}|{src}"] = r
    for (model, src, name), old in olds.items():  # reasoning on (src *_think) minus off (same model, src without it)
        off = olds.get((model, src[:-len("_think")], name)) if src.endswith("_think") else None
        if not off:
            continue
        res = {}
        for tag in ("sys1", "sys0q", "sys0qm", "sysasof"):
            pair = {b: {"on": old[b][tag], "off": off[b][tag]} for b in old if b in off and tag in old[b] and tag in off[b]}
            dd = boot_delta(pair, "on", "off")
            if dd:
                res[tag] = dict(zip(("delta", "lo", "hi", "n"), dd))
        rows[f"{model}|{src}"][name]["old_only_think_vs_off"] = res
    if out is None:  # pairs only (clustered_ci.py)
        return rows, olds
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(rows, open(out + ".json", "w"), indent=1)
    fmt = lambda x: "  -- " if x is None else f"{x:5.2f}"
    lines = [f"{'model|src':36} {'stratum':14} {'n':>4}  none  sys0  sys1  date-in-q  Δ(sys1-sys0) [95% CI]   sys0+dateQ  Δ(sys0q-sys1)"]
    for m, r in rows.items():
        for name, v in r.items():
            d = v["d_sys"]
            lines.append(f"{m:36} {name:14} {v['n']:4} {fmt(v['none'])} {fmt(v['sys0'])} {fmt(v['sys1'])}    {fmt(v['date_in_q'])}"
                         + (f"   {d['delta']:+.2f} [{d['lo']:+.2f},{d['hi']:+.2f}]" if d else "")
                         + (f"   {fmt(v['sys0q'])}  {v['d_q_vs_sys']['delta']:+.2f} [{v['d_q_vs_sys']['lo']:+.2f},{v['d_q_vs_sys']['hi']:+.2f}]" if v.get("d_q_vs_sys") else "")
                         + (f"   qm {fmt(v.get('sys0qm'))} Δ(qm-sys1) {v['d_qm_vs_sys']['delta']:+.2f} [{v['d_qm_vs_sys']['lo']:+.2f},{v['d_qm_vs_sys']['hi']:+.2f}]" if v.get("d_qm_vs_sys") else "")
                         + (f"   outdated: sys0 {fmt(v.get('sys0_outdated'))} sys2025 {fmt(v.get('sys2025_outdated'))} q2025 {fmt(v.get('q2025_outdated'))}" if "sys2025" in v or "q2025" in v else ""))
    open(out + ".md", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return rows, olds


if __name__ == "__main__":
    main()


LABELS = {  # paper rows for the system-prompt tables
    "deepseek-flash|api": "DeepSeek-V4.1-Flash", "glm-5.3|omni": "GLM-5.3", "glm-5.3-flash|omni": "GLM-5.3-Flash",
    "claude-sonnet-5-5|claude_nothink": "Claude Sonnet 5.5", "claude-haiku-5-5|claude": "Claude Haiku 5.5",
    "claude-opus-5-5|claude": "Claude Opus 5.5", "claude-fable-5-1|claude_none": "Claude Fable 5.1", "claude-fable-5-1|claude": "Claude Fable 5.1 (default)",
    "claude-fable-5|claude": "\\quad Claude Fable 5", "claude-opus-5|claude": "\\quad Claude Opus 5",
    "claude-sonnet-5|claude": "\\quad Claude Sonnet 5", "claude-opus-4-8|claude": "\\quad Claude Opus 4.8",
    "claude-opus-4-7|claude": "\\quad Claude Opus 4.7", "gpt-5.5|omni": "GPT-5.5",
    "gpt-6-sol|orouter": "GPT-6", "gpt-6-sol|orouter_think": "GPT-6", "kimi-k3|orouter": "Kimi-K3",
    "kimi-k3|orouter_think": "Kimi-K3", "gpt-6-luna|orouter": "GPT-6-Luna", "gpt-5.6-terra|orouter": "GPT-5.6-Terra",
    "hy4-preview|orouter": "HY4", "gpt-6-luna|orouter_think": "GPT-6-Luna",
    "gpt-5.6-terra|orouter_think": "GPT-5.6-Terra", "hy4-preview|orouter_think": "HY4", "muse-spark-1.2|omni": "Muse-Spark-1.2$^\\ast$",
    "Muse-Glimmer-30B-Q8_0|gpu": "Muse-Glimmer-30B (Q8)$^\\dagger$",
}
# Rows of the core table (plain / today in sys / as of in Q), in order; reasoning on/off is measured, not assumed.
# Not rows: gpt-5.6-terra|orouter_think (reasoning requested but measured on few items, so it would duplicate the off
# row) and hy4-preview|orouter_think (15-51% empty answers at the 8,192-token limit: invalid by the 20%-empty rule).
CORE = ["deepseek-flash|api", "gpt-6-sol|orouter", "kimi-k3|orouter", "gpt-6-luna|orouter", "gpt-5.6-terra|orouter",
        "hy4-preview|orouter", "claude-sonnet-5-5|claude_nothink", "claude-haiku-5-5|claude",
        "gpt-6-sol|orouter_think", "kimi-k3|orouter_think", "gpt-6-luna|orouter_think", "glm-5.3|omni", "claude-opus-5-5|claude",
        "claude-fable-5-1|claude_none", "Muse-Glimmer-30B-Q8_0|gpu"]
# Rows of the control table: models run on every control condition.
FULL = ["deepseek-flash|api", "gpt-6-sol|orouter", "kimi-k3|orouter", "gpt-6-luna|orouter", "gpt-5.6-terra|orouter",
        "hy4-preview|orouter", "claude-sonnet-5-5|claude_nothink", "claude-haiku-5-5|claude", "claude-opus-5-5|claude",
        "claude-fable-5-1|claude_none", "Muse-Glimmer-30B-Q8_0|gpu"]


def _lab(k, short):
    lab = LABELS[k]
    if short:
        lab = lab.replace("Claude ", "").replace(" (no think)", "").replace("-30B (Q8)", "").replace("-V4.1-Flash", "")
    return lab


def reasons(d, k):
    r = (d[k].get("T1np absorbed") or {}).get("reasoning")
    return r is not None and r >= 0.5


def tex(path="results/analysis/sysprompt.json", out="results/analysis/sysprompt_table.tex", short=False):
    """Two tables, each complete. Core: T1np new-first / old-only (%) with a plain system prompt, today's date in the system
    prompt and "as of" in the question; rows grouped by whether the answers show hidden reasoning (>= 50% of the
    today-in-system answers). Controls (out with _ctrl): the same sentence moved into the question, "as of" in the system
    prompt, and a pre-reform date (T1 old-only), for the models run on all of them. Earlier Claude models are in the
    lineage table; GLM-5.3-Flash and GPT-5.5 are given in the text."""
    d = json.load(open(path))
    f = lambda x: "--" if x is None else f"{100 * x:.0f}"
    g = lambda t: "--" if not t else f"{100 * t['new_first']:.0f}/{100 * t['old_only']:.0f}"
    three = lambda k: (d[k].get("T1np absorbed") or {}).get("three", {})
    cols = ("sys0", "sys1", "sys0q", "sys0qm", "sysasof")
    core = [r"\begin{tabular}{@{}l ccccc@{}}", r"\toprule",
            r" & plain & \multicolumn{2}{c}{today is} & \multicolumn{2}{c}{as of} \\",
            r"\cmidrule(lr){3-4}\cmidrule(lr){5-6}",
            r"Model & sys & sys & Q & Q & sys \\", r"\midrule"]
    order = ("sys0", "sys1", "sys0qm", "sys0q", "sysasof")
    for on in (False, True):
        core.append(r"\multicolumn{6}{@{}l}{\textit{reasoning " + ("on" if on else "off") + r"}} \\")
        for k in CORE:
            t = three(k) if k in d else {}
            if k in d and reasons(d, k) == on and all(t.get(c) for c in cols):  # only rows with every column
                core.append(f"{_lab(k, short)} & " + " & ".join(g(t.get(c)) for c in order) + r" \\")
        if not on:
            core.append(r"\midrule")
    core += [r"\bottomrule", r"\end{tabular}"]
    open(out, "w").write("\n".join(core) + "\n")
    ctrl = [r"\begin{tabular}{@{}l cc@{}}", r"\toprule",
            r" & \multicolumn{2}{c}{2025 date in} \\", r"\cmidrule(lr){2-3}",
            r"Model & sys & Q \\", r"\midrule"]
    for k in FULL:
        if k in d:
            a = d[k].get("T1 absorbed", {})
            mark = "$^{r}$" if reasons(d, k) else ""
            ctrl.append(f"{_lab(k, short)}{mark} & {f(a.get('sys2025_outdated'))} & {f(a.get('q2025_outdated'))} \\\\")
    ctrl += [r"\bottomrule", r"\end{tabular}"]
    open(out.replace(".tex", "_ctrl.tex"), "w").write("\n".join(ctrl) + "\n")


if __name__ == "__main__":
    tex()
    tex(out="results/analysis/sysprompt_table_short.tex", short=True)
