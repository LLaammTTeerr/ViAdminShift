"""Derived date-placement item sets, built from the cue3 / cue3np sets by prefix substitution.

    sysdate     : the cue = none rows of cue3_items + cue3np_items (303 bases: 63 T6, 120 T1, 120 T1np).
    sysdate_q   : the cue = date rows of the same bases ("Tính đến tháng 10/2026, " in the question).
    sysdate_qm  : the sysdate questions with "Hôm nay là ngày 13/10/2026. " in front (the sys1 sentence moved to
                  the user turn); id suffix __datem, cue datem, qtype as in the date rows.
    sysdate_q2025 : sysdate_q with the pre-reform date "Tính đến tháng 1/2025, "; id suffix __d2025, cue d2025.
    sysdate_nosuffix : the 120 T1np cue = none questions without the answer-format suffix.

    python3 scripts/build_sysdate_items.py [--out DIR]   # writes the five files (default: results/minitest/items)
    python3 scripts/build_sysdate_items.py --check       # compares the rebuilt files with results/minitest/items
                                                         # and data/eval_sets without writing (exit 1 on a mismatch)
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, "scripts")
from minitest import SUFFIX, CUES  # noqa: E402

I = "results/minitest/items"
E = "data/eval_sets"
DATEM = "Hôm nay là ngày 13/10/2026. "
D2025 = "Tính đến tháng 1/2025, "


def load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")]


def dumps(rows):
    return "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows)


def build():
    cue3 = load(f"{I}/cue3_items.jsonl")
    cue3np = load(f"{I}/cue3np_items.jsonl")
    none = [it for it in cue3 + cue3np if it["cue"] == "none"]
    date = [it for it in cue3 + cue3np if it["cue"] == "date"]
    qm = [{**it, "id": f"{it['base']}__datem", "qtype": it["qtype"].replace("/none", "/date"),
           "question": DATEM + it["question"], "cue": "datem"} for it in none]
    q2025 = [{**it, "id": f"{it['base']}__d2025", "question": D2025 + it["question"][len(CUES["date"]):],
              "cue": "d2025"} for it in date]
    nosuffix = [{**it, "question": it["question"][: -len(SUFFIX)]} for it in cue3np
                if it["cue"] == "none" and it["question"].endswith(SUFFIX)]
    return {"sysdate_items": none, "sysdate_q_items": date, "sysdate_qm_items": qm,
            "sysdate_q2025_items": q2025, "sysdate_nosuffix_items": nosuffix}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=I)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    sets = build()
    if a.check:
        bad = 0
        for name, rows in sets.items():
            built = hashlib.sha256(dumps(rows).encode("utf-8")).hexdigest()
            for d in (I, E):
                p = f"{d}/{name}.jsonl"
                have = hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else "missing"
                ok = have == built
                bad += not ok
                print(f"{'ok  ' if ok else 'DIFF'} {p} ({len(rows)} items)")
        sys.exit(1 if bad else 0)
    os.makedirs(a.out, exist_ok=True)
    for name, rows in sets.items():
        with open(f"{a.out}/{name}.jsonl", "w", encoding="utf-8") as f:
            f.write(dumps(rows))
        print(name, len(rows))


if __name__ == "__main__":
    main()
