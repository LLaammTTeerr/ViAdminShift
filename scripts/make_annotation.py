"""Human validation of the answer scorer (minitest.label + analyze_cue.label2).

  python3 scripts/make_annotation.py make            # docs/annotation/sheet_A.csv, sheet_B.csv, key.jsonl
  python3 scripts/make_annotation.py score A.csv B.csv   # Cohen's kappa: A vs B, A vs scorer, B vs scorer

The sample is 200 answers to absorbed-ward questions (the gold and old province differ), 40 per scorer label
(correct, outdated, both_new, both_old, other), drawn round-robin over models with a fixed seed. The sheets do not show
the model or the scorer's label; both annotators get the same rows in a different order. `score` compares the
annotators with the CURRENT scorer (label2 recomputed from each row's output); key.jsonl keeps the label the row was
sampled under, and the rows whose label has changed since are listed.
"""
import collections
import csv
import glob
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
from analyze_cue import label2  # noqa: E402
from minitest import load  # noqa: E402

OUT = "docs/annotation"
LABELS = ["correct", "outdated", "both_new", "both_old", "other"]
PER_LABEL = 40
DIRS = ["api", "claude", "claude_think", "claude_nothink", "omni", "omni_full", "orouter", "sysprompt", "gpu"]


def questions():
    q = {}
    for f in glob.glob("results/minitest/items/*.jsonl"):
        for it in load(f):
            q.setdefault(it["id"], it["question"])
    return q


def pool():
    q = questions()
    by = collections.defaultdict(lambda: collections.defaultdict(list))  # label -> model -> rows
    for d in DIRS:
        for f in sorted(glob.glob(f"results/minitest/{d}/preds_*.jsonl")):
            for p in load(f):
                if p.get("numeric") or not p.get("absorbed") or not p.get("old") or p["id"] not in q:
                    continue
                if not str(p["qtype"]).startswith("T1"):
                    continue
                lab = label2(p)
                by[lab][f"{d}/{p['model']}"].append({"id": p["id"], "question": q[p["id"]], "new": "; ".join(p["gold"]),
                                                     "old": "; ".join(p["old"]), "output": (p.get("output") or "").strip(),
                                                     "model": p["model"], "src": d, "scorer": lab})
    return by


def make():
    rng = random.Random(7)
    by = pool()
    rows = []
    for lab in LABELS:
        models = sorted(by[lab])
        for m in models:
            rng.shuffle(by[lab][m])
        rng.shuffle(models)
        picked, i = [], 0
        while len(picked) < PER_LABEL and any(by[lab][m] for m in models):
            m = models[i % len(models)]
            if by[lab][m]:
                picked.append(by[lab][m].pop())
            i += 1
        rows += picked
        print(lab, len(picked), "from", len(models), "model runs")
    for k, r in enumerate(rows):
        r["row"] = f"R{k + 1:03d}"
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/key.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    for name, seed in (("A", 1), ("B", 2)):
        order = rows[:]
        random.Random(seed).shuffle(order)
        with open(f"{OUT}/sheet_{name}.csv", "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["row", "question", "new_answer", "old_answer", "model_output", "label", "note"])
            for r in order:
                w.writerow([r["row"], r["question"], r["new"], r["old"], r["output"], "", ""])


def kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = collections.Counter(a), collections.Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n ** 2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0, po


def read(path):
    with open(path, encoding="utf-8-sig") as f:
        return {r["row"]: r["label"].strip().lower() for r in csv.DictReader(f)}


def score(pa, pb):
    kr = load(f"{OUT}/key.jsonl")
    key = {r["row"]: label2({"output": r["output"], "gold": [r["new"]], "old": [r["old"]]}) for r in kr}
    moved = [(r["row"], r["scorer"], key[r["row"]]) for r in kr if key[r["row"]] != r["scorer"]]
    print(f"{len(moved)} rows labelled differently by the current scorer than at sampling:", moved)
    A, B = read(pa), read(pb)
    rows = [k for k in key if A.get(k) in LABELS and B.get(k) in LABELS]
    print(f"{len(rows)} rows labelled by both (of {len(key)})")
    for name, x, y in (("A vs B", A, B), ("A vs scorer", A, key), ("B vs scorer", B, key)):
        k, po = kappa([x[r] for r in rows], [y[r] for r in rows])
        print(f"{name}: kappa {k:.2f}, agreement {po:.0%}")
    # the paper's two summary metrics: new-first (correct + both_new) and old-only (outdated)
    coarse = lambda l: "new_first" if l in ("correct", "both_new") else ("old_only" if l == "outdated" else "rest")
    for name, x in (("A", A), ("B", B)):
        k, po = kappa([coarse(x[r]) for r in rows], [coarse(key[r]) for r in rows])
        print(f"{name} vs scorer on new-first / old-only / rest: kappa {k:.2f}, agreement {po:.0%}")
    dis = collections.Counter((A[r], key[r]) for r in rows if A[r] != key[r])
    print("A vs scorer disagreements:", dis.most_common(8))


if __name__ == "__main__":
    if sys.argv[1] == "make":
        make()
    else:
        score(sys.argv[2], sys.argv[3])
