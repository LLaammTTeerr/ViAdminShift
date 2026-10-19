"""The stratified 1,262-item subset of the benchmark (data/benchmark/items_sub1k.jsonl) and its complement
(data/benchmark/items_rest.jsonl, 6,733 items).

    uv run python scripts/make_sub1k.py            # rewrites both files; --check only compares

Sampling unit: a question group, i.e. all items whose id has the same part before "__" (the cue or diacritic variants
of one question stay together). Strata: (qtype, format). Strata are visited in sorted order with one
random.Random(13); a stratum with at most 40 groups is kept whole, a larger one contributes
max(40, round(0.125 * groups)) groups, drawn with rng.sample from its sorted group keys. Both files keep the row order
and the exact lines of data/benchmark/items.jsonl.
"""
import collections
import json
import random
import sys

ITEMS, SUB, REST = "data/benchmark/items.jsonl", "data/benchmark/items_sub1k.jsonl", "data/benchmark/items_rest.jsonl"


def main():
    lines = [l for l in open(ITEMS, encoding="utf-8") if l.strip()]
    its = [json.loads(l) for l in lines]
    groups = collections.defaultdict(list)
    for i in its:
        groups[(i["qtype"], i["format"], i["id"].split("__")[0])].append(i)
    strata = collections.defaultdict(list)
    for k in groups:
        strata[k[:2]].append(k)
    rng = random.Random(13)
    ids = set()
    for _, ks in sorted(strata.items()):
        ks = sorted(ks)
        n = len(ks) if len(ks) <= 40 else max(40, round(len(ks) * 0.125))
        for k in rng.sample(ks, n):
            ids.update(i["id"] for i in groups[k])
    sub = "".join(l for l, i in zip(lines, its) if i["id"] in ids)
    rest = "".join(l for l, i in zip(lines, its) if i["id"] not in ids)
    if "--check" in sys.argv:
        ok = all(open(p, encoding="utf-8").read() == s for p, s in ((SUB, sub), (REST, rest)))
        print("identical" if ok else "DIFFERENT")
        return 0 if ok else 1
    for p, s in ((SUB, sub), (REST, rest)):
        open(p, "w", encoding="utf-8").write(s)
    print(f"{sub.count(chr(10))} subset items, {rest.count(chr(10))} rest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
