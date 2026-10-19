"""Closed-book analyses on the released benchmark (reviewer requests): the 2x2 cells, surface-vs-deep consistency, and
the per-type table without T4/T5 items whose gold ward name already occurs in the question ("leaked" items).

Inputs: results/bench/*/predictions.jsonl (the full 7,995 items for the seven small models, Muse-Glimmer and
DeepSeek-V4.1-Flash; Muse's 1,262-item subset run is skipped). The 2x2 cells and consistency use every item; the per-type table uses the
1,262-item subset, as in the appendix. Outputs: results/analysis/bench_extra.json, cells_table.tex, qtype_table.tex
(replaces analyze_rag.qtype_tex: same layout, leaked T4/T5 items removed, n per column), leaked_items.txt (their ids).

  python3 scripts/analyze_bench_extra.py
"""
import collections
import glob
import json
import os
import sys
import unicodedata

sys.path.insert(0, "scripts")
from minitest import norm  # noqa: E402

ITEMS = "data/benchmark/items.jsonl"
SUB = "data/benchmark/items_sub1k.jsonl"
WARD = ("T1_membership", "T4_address", "T5_ward_successor")
QTYPES = [("T0_headline", "T0"), ("T1_membership", "T1"), ("T1_newname", "T1n"), ("T2_composition", "T2"),
          ("T3_existence", "T3"), ("T4_address", "T4"), ("T5_ward_successor", "T5"), ("T6_reverse", "T6")]
CELLS = [((False, False), "kept / kept"), ((False, True), "kept / changed"), ((True, False), "merged / kept"),
         ((True, True), "merged / changed")]


def load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def fold(s):
    """norm() without diacritics ('Hòa' = 'Hoà' = 'Hoa')."""
    s = unicodedata.normalize("NFD", norm(s).replace("đ", "d"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def leaked(it):
    """T4/T5 item with a changed answer whose new ward name occurs in the question, e.g. new ward 'Phường Mường Lay'
    asked about a ward of 'thị xã Mường Lay', so the answer can be copied. Uses the generator's flag
    gold_name_in_question (src/viadmin/gen/items.py, hint_in_question: bare name, no diacritics, so it covers the
    diacritic-free T4 twins and names inside hyphenated ones such as 'Phan Rang-Tháp Chàm'). A ward that kept its name
    is not a leak: a T4 address must contain it, and the part that changed, the province, is not in the question."""
    m = it["meta"]
    if not it["qtype"].startswith(("T4", "T5")) or not m.get("surface_answer_changed", True):
        return False
    if not m.get("gold_name_in_question"):
        return False
    return fold(m.get("new_ward_name", "")) != fold(m.get("old_ward_name", ""))


def runs():
    """model -> (predictions on closed-book items, set of item ids the model answered)"""
    out = {}
    for f in sorted(glob.glob("results/bench/*/predictions.jsonl")):
        m = os.path.basename(os.path.dirname(f))
        if m.startswith("_") or m.endswith("-sub1k"):
            continue
        ps = [p for p in load(f) if p["condition"] == "closed"]
        name = m.replace("-full", "")
        out[name] = ps
    return out


def rate(ps, lab):
    return sum(p["label"] == lab for p in ps) / len(ps) if ps else None


def main():
    items = {i["id"]: i for i in load(ITEMS)}
    sub = {i["id"] for i in load(SUB)}
    res = {"leaked": {"all": sum(leaked(i) for i in items.values()),
                      "sub1k": sum(leaked(items[k]) for k in sub)}, "models": {}}
    for model, ps in runs().items():
        ps = [p for p in ps if p["item_id"] in items]
        r = {"n": len(ps)}
        # 2x2 cells on ward-level items, leaked items removed
        cells = collections.defaultdict(list)
        for p in ps:
            it = items[p["item_id"]]
            if it["qtype"] in WARD and not leaked(it):
                cells[(it["meta"]["province_changed"], it["meta"]["ward_changed"])].append(p)
        r["cells"] = {lab: {"n": len(cells[k]), "correct": rate(cells[k], "correct"), "outdated": rate(cells[k], "outdated")}
                      for k, lab in CELLS}
        # consistency: per old province, T6 (surface) correct vs T1 (deep) items of the same province
        t6 = collections.defaultdict(list)
        t1 = collections.defaultdict(list)
        for p in ps:
            it = items[p["item_id"]]
            g = it["meta"].get("consistency_group")
            # only provinces whose name changed: for a merged province that gave its name to the new one, T6 and T1
            # have the unchanged answer and would count as "known" trivially
            if g is None or not it["meta"].get("surface_answer_changed"):
                continue
            if it["qtype"] == "T6_reverse":
                t6[g].append(p["label"] == "correct")
            elif it["qtype"] == "T1_membership":
                t1[g].append(p["label"] == "correct")
        known = [g for g in t6 if g in t1 and sum(t6[g]) / len(t6[g]) >= 0.5]
        unknown = [g for g in t6 if g in t1 and sum(t6[g]) / len(t6[g]) < 0.5]
        acc = lambda gs: (sum(sum(t1[g]) for g in gs) / sum(len(t1[g]) for g in gs)) if gs else None
        r["consistency"] = {"groups_surface_known": len(known), "groups_surface_unknown": len(unknown),
                            "t1_acc_if_surface_known": acc(known), "t1_acc_if_surface_unknown": acc(unknown)}
        # per-type table, leaked removed
        ch, un = collections.defaultdict(collections.Counter), collections.Counter()
        for p in ps:
            it = items[p["item_id"]]
            if leaked(it) or p["item_id"] not in sub:
                continue
            if it["meta"].get("surface_answer_changed") is False:
                un[p["label"]] += 1
            else:
                ch[it["qtype"]][p["label"]] += 1
        r["qtype"] = {q: {"n": sum(ch[q].values()), "correct": ch[q]["correct"] / max(1, sum(ch[q].values())),
                          "outdated": ch[q]["outdated"] / max(1, sum(ch[q].values()))} for q, _ in QTYPES}
        r["unchanged_correct"] = un["correct"] / max(1, sum(un.values()))
        res["models"][model] = r
    res["leak_effect"] = leak_effect(items, sub)
    os.makedirs("results/analysis", exist_ok=True)
    json.dump(res, open("results/analysis/bench_extra.json", "w"), indent=1, ensure_ascii=False)
    with open("results/analysis/leaked_items.txt", "w") as f:
        f.writelines(f"{k}\n" for k in sorted(k for k, i in items.items() if leaked(i)))
    tex(res)
    print(json.dumps(res["leaked"]))
    print("leak effect (max |acc with - acc without|, points):", json.dumps(res["leak_effect"]["max"]))
    for m, r in res["models"].items():
        print(m, {k: f"{100 * v['correct']:.0f}/{100 * v['outdated']:.0f} n={v['n']}" for k, v in r["cells"].items() if v["n"]},
              r["consistency"])


def leak_effect(items, sub):
    """Accuracy per model and condition with and without the leaked items (all runs and conditions, on the 1,262-item
    subset and on the full set), and the largest absolute difference in points."""
    out, mx = {}, {}
    for f in sorted(glob.glob("results/bench/*/predictions.jsonl")):
        m = os.path.basename(os.path.dirname(f))
        if m.startswith("_"):
            continue
        preds = [p for p in load(f) if p["item_id"] in items]
        for scope, keep in (("sub1k", sub), ("full", None)):
            for c in sorted({p["condition"] for p in preds}):
                ps = [p for p in preds if p["condition"] == c and (keep is None or p["item_id"] in keep)]
                if not ps or (scope == "full" and len(ps) < 7000):
                    continue
                kept = [p for p in ps if not leaked(items[p["item_id"]])]
                a, b = rate(ps, "correct"), rate(kept, "correct")
                out[f"{m}|{scope}|{c}"] = {"n": len(ps), "n_kept": len(kept), "acc": a, "acc_kept": b}
                mx[scope] = max(mx.get(scope, 0), round(100 * abs(a - b), 1))
    return {"runs": out, "max": mx}


def pct(x):
    return "--" if x is None else f"{100 * x:.0f}"


def tex(res):
    ms = list(res["models"])
    lab = lambda m: m.replace("-Q8_0", "").replace("-q8_0", "").replace("_", r"\_")
    rows = [r"\begin{tabular}{@{}l cccc@{}}", r"\toprule",
            r"Province / ward & " + " & ".join(l for _, l in CELLS) + r" \\", r"\midrule"]
    for m in ms:
        r = res["models"][m]
        cells = []
        for _, l in CELLS:
            c = r["cells"][l]
            cells.append(pct(c["correct"]) if l == "kept / kept" else f"{pct(c['correct'])}/{pct(c['outdated'])}")
        rows.append(f"{lab(m)} & " + " & ".join(cells) + r" \\")
    n0 = res["models"][ms[0]]["cells"]
    rows += [r"\midrule", "$n$ & " + " & ".join(str(n0[l]["n"]) for _, l in CELLS) + r" \\",
             r"\bottomrule", r"\end{tabular}"]
    open("results/analysis/cells_table.tex", "w").write("\n".join(rows) + "\n")
    q = [r"\begin{tabular}{@{}l " + "c" * len(QTYPES) + r" c@{}}", r"\toprule",
         "Model & " + " & ".join(t for _, t in QTYPES) + r" & unch. \\", r"\midrule"]
    for m in ms:
        r = res["models"][m]
        q.append(lab(m) + " & " + " & ".join(
            f"{pct(r['qtype'][k]['correct'])}/{pct(r['qtype'][k]['outdated'])}" if r["qtype"][k]["n"] else "--"
            for k, _ in QTYPES) + f" & {pct(r['unchanged_correct'])} \\\\")
    first = ms[0]
    q += [r"\midrule", "$n$ & " + " & ".join(str(res["models"][first]["qtype"][k]["n"]) for k, _ in QTYPES) + r" & \\",
          r"\bottomrule", r"\end{tabular}"]
    open("results/analysis/qtype_table.tex", "w").write("\n".join(q) + "\n")


if __name__ == "__main__":
    main()
