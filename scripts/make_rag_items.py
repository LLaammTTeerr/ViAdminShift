"""Item file for the retrieval conditions of the reduced API runs: the 1,262-item subset plus every item whose mixed
context pairs a new Wikipedia passage with an old template passage (220 on the full set, 22 of them in the subset),
so that the last column of the retrieval table is computed on the same 220 pairs for every model.

  uv run python scripts/make_rag_items.py   # -> data/benchmark/items_rag_sub.jsonl (1,460 items)
"""
import json

sub = {json.loads(l)["id"] for l in open("data/benchmark/items_sub1k.jsonl")}
wt = set()
for l in open("data/benchmark/contexts.jsonl"):
    c = json.loads(l)
    if c["condition"] == "mixed" and c.get("sources"):
        by = dict(zip(c["eras"], c["sources"]))
        if by.get("new") == "wiki" and by.get("old") == "template":
            wt.add(c["item_id"])
n = 0
with open("data/benchmark/items_rag_sub.jsonl", "w") as f:
    for l in open("data/benchmark/items.jsonl"):
        if json.loads(l)["id"] in sub | wt:
            f.write(l)
            n += 1
print(f"{n} items ({len(sub)} subset + {len(wt - sub)} wiki/template pairs) -> data/benchmark/items_rag_sub.jsonl")
