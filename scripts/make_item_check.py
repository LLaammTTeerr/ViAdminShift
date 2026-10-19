"""Sheet for checking benchmark items by hand against the resolutions.

Draws a stratified sample (N per question type, fixed seed) from data/benchmark/items.jsonl and writes one row per item:
the question, the options, the gold and the pre-reform answer as text, the mapping row the item was generated from,
and, for ward-level items, the clause of Điều 1 of the Standing Committee resolution that forms the new ward (from the
local hoatieu.vn copies; run scripts/fetch_sources.sh first). Fill in `verdict` (ok / wrong / unclear) and `note`.

  uv run python scripts/make_item_check.py --per-type 10 --out item_check.csv
"""
import argparse
import csv
import json
import random
import re

from viadmin.data.resolutions import clause_for

ITEMS = "data/benchmark/items.jsonl"
MAPPING = "data/processed/ward_mapping.jsonl"
WARDS_NEW = "data/processed/wards_new.jsonl"
PROVINCE_SOURCE = "Nghị quyết 202/2025/QH15 (12/6/2025), Điều 1"


def load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def as_text(it, ans):
    """MCQ letter -> option text."""
    if it["format"] == "mcq" and isinstance(ans, str) and len(ans) == 1 and ans.isalpha():
        return f"{ans}. {it['choices'][ord(ans) - 65]}"
    return ans


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-type", type=int, default=10)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--out", default="item_check.csv")
    a = ap.parse_args()

    by_old = {r["old_ward_code"]: r for r in load(MAPPING)}
    new = {w["code"]: w for w in load(WARDS_NEW)}
    by_type = {}
    for it in load(ITEMS):
        by_type.setdefault(it["qtype"], []).append(it)
    rng = random.Random(a.seed)
    rows = []
    for qt in sorted(by_type):
        for it in rng.sample(by_type[qt], min(a.per_type, len(by_type[qt]))):
            m = it["meta"]
            r = by_old.get(m.get("old_ward_code"))
            row = {"id": it["id"], "qtype": qt, "question": it["question"],
                   "options": " | ".join(f"{chr(65 + k)}. {c}" for k, c in enumerate(it.get("choices") or [])),
                   "gold": as_text(it, it["answer"]), "old_answer": as_text(it, it["old_answer"]),
                   "mapping": "", "source": PROVINCE_SOURCE, "clause": "", "verdict": "", "note": ""}
            if r:
                row["mapping"] = (f"{r['old_ward_name']}, {r['old_district_name']}, {r['old_province_name']} -> "
                                  f"{r['new_ward_name']}, {r['new_province_name']} ({r['change_type']})")
                nw = new.get(r["new_ward_code"], {})
                num = re.match(r"\d+", nw.get("resolution") or "")
                if num:
                    hit = clause_for(num.group(0), nw["short_name"])
                    row["source"] = f"Nghị quyết {nw['resolution']}" + (f", Điều 1 khoản {hit[0]}" if hit else "")
                    row["clause"] = hit[1] if hit else "(clause not found: read Điều 1 of the resolution)"
            rows.append(row)
    with open(a.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} items -> {a.out}")


if __name__ == "__main__":
    main()
