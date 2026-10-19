"""Merge Muse-Glimmer Q8 benchmark runs into one full-set directory (closed and rag_mixed on all 7,995 items).

Sources: the 1,262-item subset run (results/bench/Muse-Glimmer-30B-Q8_0-sub1k) and the runs on the remaining items,
pulled from vast into a staging directory: rest (rag_mixed on all rest items, closed on items_rest_b), rest-B (closed,
items_rest_a forward) and rest-A2 (closed, items_rest_a reversed). Deduplicated by (item_id, condition), first seen wins.

    python3 scripts/merge_muse_full.py STAGING_DIR
"""
import collections
import json
import os
import sys

KEEP = {"closed", "rag_mixed"}  # rag_new and rag_mixed+date exist only on the subset
srcs = ["results/bench/Muse-Glimmer-30B-Q8_0-sub1k/predictions.jsonl"] + [
    os.path.join(sys.argv[1], d, "predictions.jsonl") for d in ("rest", "rest-B", "rest-A2")]
items = {json.loads(l)["id"] for l in open("data/benchmark/items.jsonl")}
out, seen = [], set()
for f in srcs:
    for l in open(f):
        p = json.loads(l)
        k = (p["item_id"], p["condition"])
        if p["condition"] in KEEP and k not in seen:
            seen.add(k)
            out.append(p)
cov = collections.Counter(c for _, c in seen)
miss = {c: len(items - {i for i, cc in seen if cc == c}) for c in KEEP}
print("conditions", dict(cov), "missing", miss)
d = "results/bench/Muse-Glimmer-30B-Q8_0-full"
os.makedirs(d, exist_ok=True)
with open(f"{d}/predictions.jsonl", "w") as fh:
    fh.writelines(json.dumps(p, ensure_ascii=False) + "\n" for p in out)
print("wrote", len(out), "to", d)
