"""Benchmark RAG conditions: closed / rag_new / rag_mixed / rag_mixed+date per model.

Mixed-RAG results are split by the source pair of the two passages (same source: wiki/wiki or template/template;
otherwise new-passage source / old-passage source), because the passage style itself affects which one models follow.
Muse-Glimmer ran on a stratified subset (data/benchmark/items_sub1k.jsonl), so every model is also scored on that subset.

Writes results/analysis/rag.json, rag.md, rag_table.tex and qtype_table.tex; run scripts/analyze_bench_extra.py
afterwards, it rewrites qtype_table.tex without the leaked T4/T5 items (the committed version).

    python3 scripts/analyze_rag.py && python3 scripts/analyze_bench_extra.py
"""
import collections
import glob
import json
import os

CONDS = ["closed", "rag_new", "rag_mixed", "rag_mixed+date"]


def load(p):
    return [json.loads(l) for l in open(p)]


def mixed_pair():
    """item_id -> 'same' | 'new=<src>/old=<src>' for the mixed context."""
    out = {}
    for c in load("data/benchmark/contexts.jsonl"):
        if c["condition"] != "mixed" or not c.get("sources"):
            continue
        by = {e: s for e, s in zip(c["eras"], c["sources"])}
        out[c["item_id"]] = "same" if len(set(c["sources"])) == 1 else f"new={by.get('new')}/old={by.get('old')}"
    return out


def stat(ps):
    n = len(ps)
    if not n:
        return None
    lab = collections.Counter(p["label"] for p in ps)
    return {"n": n, "acc": lab["correct"] / n, "outdated": lab["outdated"] / n}


def main(root="results/bench", out="results/analysis/rag"):
    pair = mixed_pair()
    sub = {i["id"] for i in load("data/benchmark/items_sub1k.jsonl")}
    res = {}
    for f in sorted(glob.glob(f"{root}/*/predictions.jsonl")):
        model = os.path.basename(os.path.dirname(f))
        if model.startswith("_"):
            continue
        preds = load(f)
        for scope, keep in (("full", None), ("sub1k", sub)):
            ps = [p for p in preds if keep is None or p["item_id"] in keep]
            r = {}
            for c in CONDS:
                pc = [p for p in ps if p["condition"] == c]
                if not pc:
                    continue
                r[c] = stat(pc)
                if c.startswith("rag_mixed"):
                    for k in sorted({pair.get(p["item_id"], "none") for p in pc}):
                        r[f"{c}|{k}"] = stat([p for p in pc if pair.get(p["item_id"], "none") == k])
            # a model is only reported on the full set if it answered (nearly) all of it
            if r and not (scope == "full" and model.endswith("-sub1k")):
                res[f"{model}|{scope}"] = r
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(res, open(out + ".json", "w"), indent=1)
    lines = []
    for m, r in res.items():
        lines.append(m)
        for k, v in r.items():
            lines.append(f"   {k:42} n={v['n']:5}  acc={v['acc']:.2f}  outdated={v['outdated']:.2f}")
    open(out + ".md", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))



def tex(path="results/analysis/rag.json", out="results/analysis/rag_table.tex", scope="sub1k"):
    """Correct / outdated (%) per condition on the shared subset; mixed conditions on same-source pairs, plus the
    cross-source pairs where the new passage is Wikipedia and the old one a template."""
    d = json.load(open(path))
    f = lambda v: "--" if not v else f"{100 * v['acc']:.0f} / {100 * v['outdated']:.0f}"
    rows = [r"\begin{tabular}{@{}l ccccc@{}}", r"\toprule",
            r" & & & \multicolumn{2}{c}{mixed, same source} & mixed \\",
            r"\cmidrule(lr){4-5}",
            r"Model & closed & new & plain & +date & new wiki, old tpl. (full) \\", r"\midrule"]
    for k, r in d.items():
        m, sc = k.rsplit("|", 1)
        if sc != scope or m.endswith("-full"):  # merged full-set runs only feed the last column
            continue
        base = m.replace("-sub1k", "")
        full = d.get(f"{base}|full") or d.get(f"{base}-full|full") or {}
        rows.append(f"{base.replace('_', chr(92) + '_')} & {f(r.get('closed'))} & {f(r.get('rag_new'))} & "
                    f"{f(r.get('rag_mixed|same'))} & {f(r.get('rag_mixed+date|same'))} & {f(full.get('rag_mixed|new=wiki/old=template'))} \\\\")
    rows += [r"\bottomrule", r"\end{tabular}"]
    open(out, "w").write("\n".join(rows) + "\n")



QTYPES = [("T0_headline", "T0"), ("T1_membership", "T1"), ("T1_newname", "T1n"), ("T2_composition", "T2"),
          ("T3_existence", "T3"), ("T4_address", "T4"), ("T5_ward_successor", "T5"), ("T6_reverse", "T6")]


def qtype_tex(root="results/bench", out="results/analysis/qtype_table.tex"):
    """Closed-book correct / outdated (%) per question type on the 1,262-item subset, on items whose answer changed
    (all items for T0/T2, which have no unchanged counterpart); last column: correct on unchanged items, all types."""
    items = {i["id"]: i for i in load("data/benchmark/items.jsonl")}
    sub = {i["id"] for i in load("data/benchmark/items_sub1k.jsonl")}
    rows = [r"\begin{tabular}{@{}l " + "c" * len(QTYPES) + r" c@{}}", r"\toprule",
            "Model & " + " & ".join(t for _, t in QTYPES) + r" & unch. \\", r"\midrule"]
    n = collections.Counter()
    for f in sorted(glob.glob(f"{root}/*/predictions.jsonl")):
        model = os.path.basename(os.path.dirname(f))
        if model.startswith("_") or model.endswith("-full"):
            continue
        ch, un = collections.defaultdict(collections.Counter), collections.Counter()
        for p in load(f):
            if p["condition"] != "closed" or p["item_id"] not in sub:
                continue
            it = items[p["item_id"]]
            if it["meta"].get("surface_answer_changed") is False:
                un[p["label"]] += 1
            else:
                ch[it["qtype"]][p["label"]] += 1
        cells = []
        for q, _ in QTYPES:
            t = sum(ch[q].values())
            n[q] = t
            cells.append(f"{100 * ch[q]['correct'] / t:.0f}/{100 * ch[q]['outdated'] / t:.0f}" if t else "--")
        cells.append(f"{100 * un['correct'] / sum(un.values()):.0f}")
        rows.append(model.replace("-sub1k", "").replace("_", r"\_") + " & " + " & ".join(cells) + r" \\")
    rows += [r"\midrule", "$n$ & " + " & ".join(str(n[q]) for q, _ in QTYPES) + r" & \\", r"\bottomrule", r"\end{tabular}"]
    open(out, "w").write("\n".join(rows) + "\n")


if __name__ == "__main__":
    main()  # rag.json, rag.md
    tex()  # rag_table.tex
    qtype_tex()  # qtype_table.tex, then overwritten by analyze_bench_extra.py (leaked items removed)
