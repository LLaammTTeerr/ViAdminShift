"""Count tables + examples for docs/benchmark_report.md.

``uv run python -m viadmin.gen.report`` prints Markdown sections (pasted into the report)."""

from __future__ import annotations

from collections import Counter, defaultdict

from viadmin.gen.common import BENCH, load_jsonl
from viadmin.gen.items import cell

CELLS = ("pc0_wc0", "pc0_wc1", "pc1_wc0", "pc1_wc1", "na")


def table(header: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" if i == 0 else "---:" for i in range(len(header))) + "|"]
    out += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    return "\n".join(out)


def main() -> None:
    items = load_jsonl(BENCH / "items.jsonl")
    ctx = load_jsonl(BENCH / "contexts.jsonl")
    passages = {p["passage_id"]: p for p in load_jsonl(BENCH / "template_passages.jsonl")}
    by_id = {it["id"]: it for it in items}

    print("### Items per qtype x format x cue\n")
    c = Counter((it["qtype"], it["format"], it["meta"].get("cue") or "-") for it in items)
    rows = [[q, f, cu, n] for (q, f, cu), n in sorted(c.items())]
    print(table(["qtype", "format", "cue", "items"], rows), "\n")
    print(f"Total items: {len(items)}\n")

    print("### Items per qtype x 2x2 cell x format (all cues and twins counted)\n")
    c = Counter((it["qtype"], it["format"], cell(it["meta"].get("province_changed"), it["meta"].get("ward_changed")))
                for it in items)
    keys = sorted({(q, f) for q, f, _ in c})
    rows = [[q, f] + [c.get((q, f, cl), 0) for cl in CELLS] for q, f in keys]
    print(table(["qtype", "format", *CELLS], rows), "\n")

    print("### Base items (cue=none, diacritised) per cell, with old_answer set / surface changed\n")
    rows = []
    for q in sorted({it["qtype"] for it in items}):
        base = [it for it in items if it["qtype"] == q and it["meta"].get("cue") in (None, "none")
                and it["meta"].get("has_diacritics") is not False]
        for cl in CELLS:
            b = [it for it in base if cell(it["meta"].get("province_changed"), it["meta"].get("ward_changed")) == cl]
            if not b:
                continue
            rows.append([q, cl, len(b), sum(it["old_answer"] is not None for it in b),
                         sum(bool(it["meta"].get("surface_answer_changed")) for it in b)])
    print(table(["qtype", "cell", "base items", "old_answer set", "surface_answer_changed"], rows), "\n")

    print("### T3_existence by entity kind and gold\n")
    c = Counter((it["meta"]["entity_kind"], it["meta"]["t3_gold_kind"], it["old_answer"] is not None)
                for it in items if it["qtype"] == "T3_existence")
    print(table(["entity_kind", "gold (P/D/W=exists at level, N=no)", "old_answer set", "n"],
                [[a, b, o, n] for (a, b, o), n in sorted(c.items())]), "\n")
    t3 = Counter(it["meta"]["t3_exists"] for it in items if it["qtype"] == "T3_existence")
    print(f"T3 exists / not: {t3[True]} / {t3[False]}\n")

    print("### T1_newname categories (base items)\n")
    c = Counter(("reused, old answer identifiable" if it["meta"]["old_answer_province"] else
                 ("reused, same province name" if it["meta"]["name_reused_from_old"] else "new name"),
                 cell(it["meta"]["province_changed"], it["meta"]["ward_changed"]))
                for it in items if it["qtype"] == "T1_newname" and it["meta"]["cue"] == "none")
    print(table(["category", "cell", "n"], [[a, b, n] for (a, b), n in sorted(c.items())]), "\n")

    print("### T4 twins (no-diacritic copies) per cell\n")
    c = Counter(cell(it["meta"]["province_changed"], it["meta"]["ward_changed"]) for it in items
                if it["qtype"] == "T4_address" and it["meta"]["has_diacritics"] is False)
    print(table(["cell", "twins"], [[k, v] for k, v in sorted(c.items())]), "\n")

    print("### Gold ward name occurs in the question (new ward named after the old district etc.)\n")
    rows = []
    for q in ("T4_address", "T5_ward_successor"):
        b = [it for it in items if it["qtype"] == q and it["meta"].get("cue") in (None, "none")
             and it["meta"].get("has_diacritics") is not False and (q != "T5_ward_successor" or it["format"] == "short")]
        for cl in CELLS:
            bb = [it for it in b if cell(it["meta"]["province_changed"], it["meta"]["ward_changed"]) == cl]
            if bb:
                k = sum(bool(it["meta"].get("gold_name_in_question")) for it in bb)
                rows.append([q, cl, len(bb), k, f"{k / len(bb):.1%}"])
    print(table(["qtype", "cell", "base items", "gold name in question", "rate"], rows), "\n")

    print("### Context sources (passage of the `new` condition; old passage of `mixed`)\n")
    c = Counter()
    for r in ctx:
        q = by_id[r["item_id"]]["qtype"]
        if r["condition"] == "new":
            c[(q, "new", r["sources"][0])] += 1
        elif r["condition"] == "mixed":
            c[(q, "mixed-old", r["sources"][r["eras"].index("old")])] += 1
    rows = []
    for q in sorted({k[0] for k in c}):
        rows.append([q, c[(q, "new", "wiki")], c[(q, "new", "template")], c[(q, "mixed-old", "wiki")],
                     c[(q, "mixed-old", "template")]])
    print(table(["qtype", "new: wiki", "new: template", "mixed old: wiki", "mixed old: template"], rows), "\n")
    pc = Counter((p["source"], p["era"], p["entity_set"]) for p in passages.values())
    print(table(["passage source", "era", "entity_set", "n"], [[a, b, s, n] for (a, b, s), n in sorted(pc.items(), key=str)]), "\n")
    ml = [sum(len(passages[x]["text"]) for x in r["passages"]) for r in ctx if r["condition"] == "mixed"]
    nl = [len(passages[r["passages"][0]]["text"]) for r in ctx if r["condition"] == "new"]
    print(f"Context length (chars): new mean {sum(nl) / len(nl):.0f} max {max(nl)}; "
          f"mixed mean {sum(ml) / len(ml):.0f} max {max(ml)}\n")
    first = Counter(r["eras"][0] for r in ctx if r["condition"] == "mixed")
    print(f"Mixed order: old passage first in {first['old']}, new first in {first['new']} rows\n")

    print("### MCQ answer letters per qtype\n")
    c: dict[str, Counter] = defaultdict(Counter)
    for it in items:
        if it["format"] == "mcq":
            c[it["qtype"]][it["answer"]] += 1
    print(table(["qtype", "A", "B", "C", "D"], [[q, *(c[q].get(x, 0) for x in "ABCD")] for q in sorted(c)]), "\n")

    groups = Counter(it["meta"]["consistency_group"] for it in items if it["meta"].get("consistency_group"))
    t6g = {it["meta"]["consistency_group"] for it in items if it["qtype"] == "T6_reverse"}
    deep = {it["meta"]["consistency_group"] for it in items if it["qtype"] != "T6_reverse" and it["meta"].get("consistency_group")}
    print(f"consistency groups: {len(groups)} (with T6: {len(t6g)}, with T6 and >=1 other item: {len(t6g & deep)})\n")


if __name__ == "__main__":
    main()
