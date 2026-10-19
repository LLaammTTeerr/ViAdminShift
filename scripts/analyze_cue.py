"""Cue-ladder analysis over every preds_cue3*.jsonl under results/minitest/<source>/.

One row per (model, source). cue3 (549) and cue3sub (2,589) predictions of the same model/source are
merged by item id (identical ids = identical questions). Per stratum and cue: accuracy and outdated
rate; deltas (date - none, reform - none) with a paired bootstrap 95% CI over bases (B=2000).

Hidden reasoning: billed completion tokens minus a visible-length estimate (~3 bytes/token for
Vietnamese). An item counts as "reasoned" if the API returned reasoning or > HIDDEN_TOK tokens are
unaccounted for. Models are labelled by this measurement, never by API flags.

    python3 scripts/analyze_cue.py [--out results/analysis/cue]
"""
import argparse
import collections
import glob
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from minitest import ALIASES, label, load, nfc, norm, short, snorm  # noqa: E402

HIDDEN_TOK = 40
CUES = ("none", "date", "reform")
STRATA = [  # (name, qtype prefix, absorbed flag)
    ("T6 prov absorbed", "T6_province", True), ("T6 prov kept", "T6_province", False),
    ("T1 ward absorbed", "T1_ward_province", True), ("T1 ward kept", "T1_ward_province", False),
    ("T1np absorbed", "T1np_ward_province", True), ("T1np kept", "T1np_ward_province", False),  # no province in question
    ("T5 succ changed", "T5_ward_successor", True), ("T5 succ unchanged", "T5_ward_successor", False),
]
HEADLINE = "T1 ward absorbed"


def _unchanged_provinces(path="data/processed/ward_mapping.jsonl"):
    """New provinces formed from exactly one old province (the 11 untouched ones), as normalised names."""
    src = collections.defaultdict(set)
    for l in open(path):
        r = json.loads(l)
        src[short(r["new_province_name"])].add(short(r["old_province_name"]))
    return {n for n, olds in src.items() if len(olds) == 1}


UNCHANGED = _unchanged_provinces()
# "kept" units keep their province NAME; split into the 11 untouched provinces and the 23 merged provinces whose name
# survived (their units were merged but the answer string is unchanged).
KEPT_SPLIT = [("T6 prov kept", "T6"), ("T1 ward kept", "T1"), ("T1np kept", "T1np")]
SRC_ALIAS = {"omni_full": "omni"}  # same endpoint and settings; cue3sub run in a later session of the same endpoint
# Paper table rows: (model, source) -> (label, family, open weights?). Order = table order.
PAPER = {
    ("deepseek-flash", "api"): ("DeepSeek-V4.1-Flash", "DeepSeek", False),
    ("kimi-k3", "omni"): ("Kimi-K3", "Moonshot", False),
    ("glm-5.3", "omni"): ("GLM-5.3", "Zhipu", False),
    ("glm-5.3-flash", "omni"): ("GLM-5.3-Flash", "Zhipu", False),
    ("qwen3.8-flash", "omni"): ("Qwen3.8-Flash$^\\ddagger$", "Alibaba", False),
    ("claude-sonnet-5-5", "claude_nothink"): ("Claude Sonnet 5.5", "Anthropic", False),
    ("claude-haiku-5-5", "claude"): ("Claude Haiku 5.5", "Anthropic", False),
    ("claude-sonnet-5-5", "claude"): ("Claude Sonnet 5.5 (default)", "Anthropic", False),
    ("claude-haiku-5-5", "claude_think"): ("Claude Haiku 5.5 (think)", "Anthropic", False),
    ("claude-opus-5-5", "claude"): ("Claude Opus 5.5", "Anthropic", False),
    ("claude-fable-5-1", "claude_none"): ("Claude Fable 5.1", "Anthropic", False),
    ("claude-fable-5-1", "claude"): ("Claude Fable 5.1 (default)", "Anthropic", False),
    ("gpt-6-sol", "omni"): ("GPT-6", "OpenAI", False),
    ("gpt-5.5", "omni"): ("GPT-5.5", "OpenAI", False),
    ("openai/gpt-6-luna", "orouter"): ("GPT-6-Luna", "OpenAI", False),
    ("openai/gpt-5.6-terra", "orouter"): ("GPT-5.6-Terra", "OpenAI", False),
    ("tencent/hy4-preview", "orouter"): ("HY4 (preview)", "Tencent", False),
    ("x-ai/grok-4.7", "orouter"): ("Grok-4.7", "xAI", False),
    ("stepfun/step-5-preview", "orouter"): ("Step-5 (preview)", "StepFun", False),
    ("muse-spark-1.2", "omni"): ("Muse-Spark-1.2$^\\ddagger$", "Meta", False),
    ("Muse-Glimmer-30B-Q8_0", "gpu"): ("Muse-Glimmer-30B (Q8)", "Meta", True),
    ("Muse-Glimmer-30B-Q8_0-nodate", "gpu"): ("\\quad no template date", "Meta", True),
    ("deepseek-v4-pro", "api"): ("DeepSeek-V4-Pro (control)", "DeepSeek", False),
    ("qwen3.8-max", "omni"): ("Qwen3.8-Max (control)", "Alibaba", False),
}


def hidden(p):
    if p.get("reasoned"):
        return True
    ct = p.get("ctoks")
    return ct is not None and ct - len((p.get("output") or "").encode()) / 3 > HIDDEN_TOK


def first_pos(names, out):
    n = " " + snorm(nfc(out)) + " "
    cands = set()
    for x in names:
        cands.add(snorm(x))
        cands.update(ALIASES.get(short(x), []))
    hits = [n.find(f" {c} ") for c in cands if c and f" {c} " in n]
    return min(hits) if hits else 10 ** 9


def label2(p):
    """minitest.label, with 'both' split by which name the answer commits to first.

    'Tỉnh Hà Giang (từ 1/7/2025 sáp nhập vào tỉnh Tuyên Quang)' -> both_old
    'Tỉnh Tuyên Quang (trước đây là Hà Giang)'                   -> both_new
    """
    l = label(p)
    if l == "both" and not p.get("numeric"):
        return "both_new" if first_pos(p["gold"], p["output"]) < first_pos(p["old"], p["output"]) else "both_old"
    return l


def t5_invalid(p):
    """T5 probe items (item rows, with the question) that break the item rules once tone placement is ignored: a 'renamed' unit whose new name is its
    old name in the other tone spelling ('Xã Khánh Hoà' -> 'Xã Khánh Hòa'), or a new name that appears in the
    question's district or province ('Hoà An' in 'Huyện Hòa An'). build_cue3 compared spellings literally and kept
    these 8 units; the analysis leaves them out."""
    if not p["qtype"].startswith("T5_ward_successor/") or not p.get("absorbed"):
        return False
    g = snorm(p["gold"][0])
    if p["old"] and snorm(p["old"][0]) == g:
        return True
    m = re.search(r"\((.*)\) thuộc đơn vị hành chính cấp xã", p["question"])
    return bool(m) and f" {g} " in " " + " ".join(snorm(x) for x in m.group(1).split(", ")) + " "


T5_INVALID = {i["base"] for f in sorted(glob.glob("results/minitest/items/cue3*_items.jsonl")) for i in load(f) if t5_invalid(i)}


def collect(root):
    runs = collections.defaultdict(dict)
    for path in sorted(glob.glob(f"{root}/*/preds_cue3*.jsonl")):
        src = os.path.basename(os.path.dirname(path))
        src = SRC_ALIAS.get(src, src)
        full = "cue3full" in os.path.basename(path)
        for p in load(path):
            if p.get("base") in T5_INVALID and p["qtype"].startswith("T5_ward_successor/"):
                continue
            k = (p["model"], src)
            if full or p["id"] not in runs[k]:
                runs[k][p["id"]] = p
    return runs


def boot_delta(by_base, a, b, B=2000, seed=0):
    """Paired bootstrap over bases that have both cues: mean(correct[a] - correct[b])."""
    d = [v[a] - v[b] for v in by_base.values() if a in v and b in v]
    if not d:
        return None
    rng = random.Random(seed)
    ms = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(B))
    return sum(d) / len(d), ms[int(0.025 * B)], ms[int(0.975 * B) - 1], len(d)


def _cell(ps):
    """Per-cue accuracy/labels and paired bootstrap deltas for one stratum."""
    cell, by_base, by_base_new = {}, collections.defaultdict(dict), collections.defaultdict(dict)
    for c in CUES:
        pc = [p for p in ps if p["cue"] == c]
        if pc:
            labs = [label2(p) for p in pc]
            k = collections.Counter(labs)
            cell[c] = {"n": len(pc), "acc": k["correct"] / len(pc),  # strict, pre-registered
                       "outdated": k["outdated"] / len(pc),
                       "both_new": k["both_new"] / len(pc),  # answers new, mentions old (post-hoc)
                       "both_old": k["both_old"] / len(pc),  # answers old, mentions the change (post-hoc)
                       "other": k["other"] / len(pc),  # neither name: wrong / refusal / invalid
                       "hidden": sum(map(hidden, pc)) / len(pc)}
            for p, l in zip(pc, labs):
                by_base[p["base"]][c] = float(l == "correct")
                by_base_new[p["base"]][c] = float(l in ("correct", "both_new"))
    for c in ("date", "reform"):
        r = boot_delta(by_base, c, "none")
        if r:
            cell[f"d_{c}"] = dict(zip(("delta", "lo", "hi", "n"), r))
        r = boot_delta(by_base_new, c, "none")
        if r:
            cell[f"d_{c}_new1st"] = dict(zip(("delta", "lo", "hi", "n"), r))
    return cell


def analyse(preds, visible_only=False):
    """visible_only: keep only items with no returned and no hidden reasoning (per-item no-reasoning analysis)."""
    preds = [p for p in preds if not (visible_only and hidden(p))]
    res = {}
    for name, qt, ab in STRATA:
        ps = [p for p in preds if p["qtype"].startswith(qt + "/") and bool(p.get("absorbed")) == ab]
        if not ps:
            continue
        cell = _cell(ps)
        res[name] = cell
        if name in dict(KEPT_SPLIT):
            for sub, keep in (("unmerged", True), ("merged", False)):
                sp = [p for p in ps if (short(p["gold"][0]) in UNCHANGED) == keep]
                if sp:
                    res[f"{name} {sub}"] = _cell(sp)
    allp = list(preds)
    res["_meta"] = {"n": len(allp), "empty": sum(not (p.get("output") or "").strip() for p in allp) / max(len(allp), 1),
                    "hidden_all": sum(map(hidden, allp)) / max(len(allp), 1)}
    h = res.get(HEADLINE, {}).get("reform")
    # pre-registered: >20% empty outputs = invalid run (reasoning ate the token budget), not a knowledge result
    res["_meta"]["valid"] = res["_meta"]["empty"] <= 0.20
    res["_meta"]["knows"] = bool(res["_meta"]["valid"] and h and h["acc"] >= 0.5)
    # pre-registered premise-leak control: |reform - none| < 0.10 on kept/control items
    kept = [res[k]["d_reform"]["delta"] for k in ("T6 prov kept", "T1 ward kept", "T1np kept") if k in res and "d_reform" in res[k]]
    res["_meta"]["kept_max_abs_d"] = max(map(abs, kept)) if kept else None
    res["_meta"]["kept_ok"] = bool(kept) and max(map(abs, kept)) < 0.10
    return res


def fmt_d(d):
    return f"{d['delta']:+.2f} [{d['lo']:+.2f},{d['hi']:+.2f}]" if d else "–"


def table(results):
    rows = ["| model [source] | n | knows | hidden% | stratum | none | date | reform | Δ date | Δ reform |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    order = sorted(results, key=lambda k: (not results[k]["_meta"]["knows"],
                                           -results[k].get(HEADLINE, {}).get("reform", {}).get("acc", 0)))
    for k in order:
        r, m = results[k], results[k]["_meta"]
        first = True
        for name, *_ in STRATA:
            if name not in r:
                continue
            cell = r[name]
            acc = [f"{cell[c]['acc']:.2f}"
                   + (f" n1 {cell[c]['acc'] + cell[c]['both_new']:.2f}" if cell[c]['both_new'] >= 0.05 else "")
                   + (f" aw {cell[c]['acc'] + cell[c]['both_new'] + cell[c]['both_old']:.2f}" if cell[c]['both_old'] >= 0.05 else "")
                   + (f" oth {cell[c]['other']:.2f}" if cell[c]['other'] >= 0.10 else "")
                   + (f" ({cell[c]['hidden']:.0%}h)" if cell[c]['hidden'] >= 0.05 else "")
                   if c in cell else "–" for c in CUES]
            head = (f"{k[0]} [{k[1]}] | {m['n']} | {'Y' if m['knows'] else 'n'} | {m['hidden_all']:.0%}"
                    + (f" EMPTY {m['empty']:.0%}" if m["empty"] > 0.05 else "")) if first else " | | |"
            n_ab = cell.get("reform", cell.get("none", {})).get("n", 0)
            rows.append(f"| {head} | {name} (n={n_ab}) | " + " | ".join(acc)
                        + f" | {fmt_d(cell.get('d_date'))} | {fmt_d(cell.get('d_reform'))} |")
            first = False
    return "\n".join(rows)


def pp(x):
    """Signed percentage points, no '-0'."""
    v = round(100 * x)
    return f"${v:+d}$" if v else "$0$"


def tex(results):
    """Headline table: strict accuracy on absorbed wards, with and without the province in the question, plus the
    pre-registered kept-province control (reform - none on units whose province was NOT merged; bold if |.| >= 10)."""
    def acc(c, k):
        return f"{100 * c[k]['acc']:.0f}" if c and k in c else "--"

    def dl(c, k="d_reform"):
        d = c.get(k) if c else None
        return f"{pp(d['delta'])} {{\\scriptsize[{100 * d['lo']:.0f},{100 * d['hi']:.0f}]}}" if d else "--"

    def kept(c):
        """date / reform change on kept units; bold if either |.| >= 10."""
        if not c or not c.get("d_reform"):
            return "--"
        ds = [c.get(k) for k in ("d_date", "d_reform")]
        v = "/".join(pp(d["delta"]) if d else "--" for d in ds)
        return f"\\textbf{{{v}}}" if any(d and abs(d["delta"]) >= 0.10 for d in ds) else v
    def none_cell(c):
        """strict correct / old-only at cue none (strict accuracy alone hides dual answers)."""
        return f"{100 * c['none']['acc']:.0f}/{100 * c['none']['outdated']:.0f}" if c and "none" in c else "--"

    def d0(c, k="d_reform"):
        d = c.get(k) if c else None
        return pp(d['delta']) if d else "--"
    out = [r"\begin{tabular}{@{}l r r ccc cc c ccc cc c@{}}", r"\toprule",
           r" & & & \multicolumn{6}{c}{address with old province (T1)} & \multicolumn{6}{c}{address without province (T1np)} \\",
           r"\cmidrule(lr){4-9}\cmidrule(lr){10-15}",
           r"Model & $n$ & hid.\% & none c/o & date & reform & $\Delta_{\text{date}}$ & $\Delta_{\text{ref.}}$ & kept d/r & none c/o & date & reform & $\Delta_{\text{date}}$ & $\Delta_{\text{ref.}}$ & kept d/r \\",
           r"\midrule"]
    for key, (lab, fam, open_w) in PAPER.items():
        r = results.get(key)
        if not r:
            continue
        a, b = r.get("T1 ward absorbed"), r.get("T1np absorbed")
        ka, kb = r.get("T1 ward kept"), r.get("T1np kept")
        hid = 100 * sum(a[c]["hidden"] * a[c]["n"] for c in CUES if c in a) / sum(a[c]["n"] for c in CUES if c in a)
        out.append(f"{lab}{'$^\\dagger$' if open_w else ''} & {a['none']['n']} & {hid:.0f} & {none_cell(a)} & {acc(a, 'date')} & "
                   f"{acc(a, 'reform')} & {dl(a, 'd_date')} & {d0(a)} & {kept(ka)} & {none_cell(b)} & {acc(b, 'date')} & {acc(b, 'reform')} & {dl(b, 'd_date')} & {d0(b)} & {kept(kb)} \\\\")
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out) + "\n"


SHORT_SKIP = {("claude-fable-5-1", "claude"), ("claude-sonnet-5-5", "claude")}  # second reasoning setting, in the full table only


def short_tex(results):
    """6-page version of the headline table: valid gate-passing rows only, fewer columns."""
    def acc(c, k):
        return f"{100 * c[k]['acc']:.0f}" if c and k in c else "--"

    def co(c):
        return f"{100 * c['none']['acc']:.0f}/{100 * c['none']['outdated']:.0f}" if c and "none" in c else "--"

    def kept(c):
        if not c or not c.get("d_reform"):
            return "--"
        ds = [c.get(k) for k in ("d_date", "d_reform")]
        v = "/".join(pp(d["delta"]) if d else "--" for d in ds)
        return f"\\textbf{{{v}}}" if any(d and abs(d["delta"]) >= 0.10 for d in ds) else v
    out = [r"\begin{tabular}{@{}l ccc c ccc@{}}", r"\toprule",
           r" & \multicolumn{4}{c}{T1 (old province given)} & \multicolumn{3}{c}{T1np (no province)} \\",
           r"\cmidrule(lr){2-5}\cmidrule(lr){6-8}",
           r"Model & none c/o & date & ref. & kept d/r & none c/o & date & ref. \\", r"\midrule"]
    for key, (lab, fam, open_w) in PAPER.items():
        r = results.get(key)
        if not r or "ddagger" in lab or "(control)" in lab or "(think)" in lab or key in SHORT_SKIP:
            continue
        a, b, ka = r.get("T1 ward absorbed"), r.get("T1np absorbed"), r.get("T1 ward kept")
        lab = lab.replace("Claude ", "").replace("-30B (Q8)", "")
        out.append(f"{lab}{'$^\\dagger$' if open_w else ''} & {co(a)} & {acc(a, 'date')} & {acc(a, 'reform')} & {kept(ka)} & "
                   f"{co(b)} & {acc(b, 'date')} & {acc(b, 'reform')} \\\\")
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out) + "\n"


DEPTH = [("T6 prov absorbed", "T6"), ("T1 ward absorbed", "T1"), ("T5 succ changed", "T5")]


def depth_tex(results):
    """Depth table: strict accuracy none / reform for surface (T6), composed (T1) and deep (T5) facts, gate-passing
    models with the 2,589-item extension only."""
    out = [r"\begin{tabular}{@{}l ccc@{}}", r"\toprule", "Model & " + " & ".join(t for _, t in DEPTH) + r" \\", r"\midrule"]
    for key, (lab, fam, open_w) in PAPER.items():
        r = results.get(key)
        if not r or not r["_meta"]["knows"] or "T5 succ changed" not in r or "(control)" in lab:
            continue
        cells = []
        for st, _ in DEPTH:
            c = r.get(st, {})
            cells.append(" / ".join(f"{100 * c[q]['acc']:.0f}" if q in c else "--" for q in ("none", "reform")))
        out.append(f"{lab}{'$^\\dagger$' if open_w else ''} & " + " & ".join(cells) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out) + "\n"


# second reasoning setting of a model, marked; an unmarked row is the lowest setting (the "claude" source is the lowest
# setting for Haiku 5.5 and the default for Sonnet 5.5 and Fable 5.1)
SUFFIX = {("claude-fable-5-1", "claude"): " (default)", ("claude-sonnet-5-5", "claude"): " (default)", ("claude-haiku-5-5", "claude_think"): " (think)"}


def models_tex(results):
    """Appendix: every evaluated model with source, items, empty share and gate status."""
    src_lab = {"api": "DeepSeek API", "claude": "Anthropic API", "claude_nothink": "Anthropic API", "claude_think": "Anthropic API", "claude_none": "Anthropic API",
               "omni": "reseller", "orouter": "OpenRouter", "gpu": "local GPU", "cpu": "local CPU"}
    out = [r"\begin{tabular}{@{}l l r r r l@{}}", r"\toprule",
           r"Model & source & items & empty\% & T1 reform & status \\", r"\midrule"]
    keyf = lambda kv: (kv[0][1] in ("gpu", "cpu"), kv[0][1], kv[0][0].lower())
    for (m, src), r in sorted(results.items(), key=keyf):
        meta = r["_meta"]
        a = r.get("T1 ward absorbed", {}).get("reform")
        st = "invalid" if not meta["valid"] else ("knows" if meta["knows"] else "--")
        if meta["knows"] and not meta.get("kept_ok", True):
            st += r" (kept$\times$)"
        name = m.split("/")[-1].replace("_", r"\_") + SUFFIX.get((m, src), "")
        acc = "--" if not a else f"{100 * a['acc']:.0f}"
        out.append(f"{name} & {src_lab.get(src, src)} & {meta['n']} & {100 * meta['empty']:.0f} & {acc} & {st} \\\\")
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out) + "\n"


LOCAL_DUP = {"qwen3.8-27b"}  # reseller runs of a model that is also run locally (Qwen3.8-27B-Q8_0): counted once, as local
API_ALIAS = {"x-ai/grok-4.7": "grok-4.7", "deepseek-v4.1-flash": "deepseek-flash", "claude-haiku-4.5": "claude-haiku-4-5-20251001", "claude-opus-5.5": "claude-opus-5-5", "claude-sonnet-5.5": "claude-sonnet-5-5"}


def counts_tex(results):
    """Distinct models (quant rungs, the no-date template run and reseller re-runs of first-party models not counted)."""
    loc = {m for m, s in results if s in ("gpu", "cpu") and "-nodate" not in m and "-UD-" not in m}
    api = {API_ALIAS.get(m, m) for m, s in results if s not in ("gpu", "cpu")} - LOCAL_DUP
    know = {API_ALIAS.get(m, m) for (m, s), r in results.items() if r["_meta"]["knows"] and "-nodate" not in m and "-UD-" not in m}
    return (f"\\newcommand{{\\nLocal}}{{{len(loc)}}}\n\\newcommand{{\\nAPI}}{{{len(api)}}}\n"
            f"\\newcommand{{\\nModels}}{{{len(loc) + len(api)}}}\n\\newcommand{{\\nKnowers}}{{{len(know)}}}\n")


RUNGS = ["Q8_0", "UD-Q6_K_XL", "UD-Q5_K_M", "UD-Q4_K_XL", "UD-Q3_K_XL", "UD-Q2_K_XL", "UD-IQ2_XXS"]


def quant_tex(results):
    """Muse-Glimmer quantization ladder: strict accuracy none / date / reform on absorbed T1, kept T1, renamed T5."""
    out = [r"\begin{tabular}{@{}l ccc ccc c@{}}", r"\toprule",
           r" & \multicolumn{3}{c}{T1 absorbed} & \multicolumn{3}{c}{T1 kept} & T5 \\",
           r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}\cmidrule(lr){8-8}",
           r"Quant. & none & date & reform & none & date & reform & reform \\", r"\midrule"]
    for q in RUNGS:
        r = results.get((f"Muse-Glimmer-30B-{q}", "gpu"))
        if not r:
            continue
        f = lambda st, c: f"{100 * r[st][c]['acc']:.0f}" if st in r and c in r[st] else "--"
        out.append(f"{q.replace('UD-', '').replace('_', chr(92) + '_')} & " + " & ".join(f("T1 ward absorbed", c) for c in CUES)
                   + " & " + " & ".join(f("T1 ward kept", c) for c in CUES) + f" & {f('T5 succ changed', 'reform')} \\\\")
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out) + "\n"


LINEAGE = [("claude-haiku-4-5-20251001", "Haiku 4.5"), ("claude-opus-4-5-20251101", "Opus 4.5"), ("claude-sonnet-4-6", "Sonnet 4.6"),
           ("claude-opus-4-6", "Opus 4.6"), ("claude-opus-4-7", "Opus 4.7"), ("claude-opus-4-8", "Opus 4.8"),
           ("claude-sonnet-5", "Sonnet 5"), ("claude-opus-5", "Opus 5"), ("claude-fable-5", "Fable 5"),
           ("claude-fable-5-1", "Fable 5.1"), ("claude-haiku-5-5", "Haiku 5.5"), ("claude-sonnet-5-5", "Sonnet 5.5"),
           ("claude-opus-5-5", "Opus 5.5")]


def lineage_tex(results, sys_path="results/analysis/sysprompt.json"):
    """Claude generations (first-party API, no thinking): surface T6 at none, T1 / T1np ladder, outdated at none, gate,
    and T1np old-only with today's date in the system prompt / "as of" in the question (analyze_sys.py).
    T1np and the date-placement runs were only made for models that pass the gate (n/a otherwise)."""
    sysd = json.load(open(sys_path)) if os.path.exists(sys_path) else {}
    out = [r"\begin{tabular}{@{}l c ccc c c ccc c@{}}", r"\toprule",
           r" & T6 & \multicolumn{3}{c}{T1} & T1 & & \multicolumn{3}{c}{T1np} & old-only \\",
           r"\cmidrule(lr){3-5}\cmidrule(lr){8-10}",
           r"Claude & none & none & date & ref. & outd. & knows & none & date & ref. & sys/Q \\", r"\midrule"]
    for m, lab in LINEAGE:
        r = results.get((m, "claude_nothink")) or results.get((m, "claude_none")) or results.get((m, "claude"))
        if not r:
            continue
        knows = r["_meta"]["knows"]
        na = "--" if knows else "n/a"
        f = lambda st, c, k="acc": f"{100 * r[st][c][k]:.0f}" if st in r and c in r[st] else na
        t = ((sysd.get(f"{m}|claude_nothink") or sysd.get(f"{m}|claude_none") or sysd.get(f"{m}|claude") or {}).get("T1np absorbed") or {}).get("three", {})
        oo = lambda k: f"{100 * t[k]['old_only']:.0f}" if t.get(k) else na
        head = (f"{lab} & {f('T6 prov absorbed', 'none')} & " + " & ".join(f("T1 ward absorbed", c) for c in CUES)
                + f" & {f('T1 ward absorbed', 'none', 'outdated')} & {'yes' if knows else 'no'} & ")
        if not knows:  # T1np and date placement are only run for models that pass the gate
            out.append(head + r"\multicolumn{4}{c}{\textit{below the gate}} \\")
            continue
        out.append(head + " & ".join(f("T1np absorbed", c) for c in CUES) + f" & {oo('sys1')}/{oo('sys0q')} \\\\")
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="results/minitest")
    ap.add_argument("--out", default="results/analysis/cue")
    ap.add_argument("--knowers-only", action="store_true")
    a = ap.parse_args()
    results = {k: analyse(v.values()) for k, v in collect(a.root).items()}
    if a.knowers_only:
        results = {k: v for k, v in results.items() if v["_meta"]["knows"]}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out + ".json", "w") as f:
        json.dump({f"{m}|{s}": v for (m, s), v in results.items()}, f, indent=1)
    md = table(results)
    with open(a.out + ".md", "w") as f:
        f.write("Accuracy per cue: strict (pre-registered). Post-hoc, shown when >= 5%: n1 = answers new first (strict + new-then-old answers); aw = any mention of the new unit (n1 + old-then-new answers); oth = neither name (wrong/refusal), shown when >= 10%. (Xh) = share of items with hidden/visible reasoning. Δ = paired bootstrap 95% CI.\n\n" + md + "\n")
    with open(a.out + "_table.tex", "w") as f:
        f.write(tex(results))
    with open(os.path.join(os.path.dirname(a.out), "counts.tex"), "w") as f:
        f.write(counts_tex(results))
    with open(a.out + "_table_short.tex", "w") as f:
        f.write(short_tex(results))
    with open(a.out + "_quant.tex", "w") as f:
        f.write(quant_tex(results))
    with open(a.out + "_depth.tex", "w") as f:
        f.write(depth_tex(results))
    with open(a.out + "_models.tex", "w") as f:
        f.write(models_tex(results))
    with open(a.out + "_lineage.tex", "w") as f:
        f.write(lineage_tex(results))
    # per-item no-reasoning analysis (items with neither returned nor hidden reasoning), for the generality claim
    vis = {k: analyse(v.values(), visible_only=True) for k, v in collect(a.root).items()}
    with open(a.out + "_noreason.json", "w") as f:
        json.dump({f"{m}|{s}": v for (m, s), v in vis.items()}, f, indent=1)
    print(md)


if __name__ == "__main__":
    main()
