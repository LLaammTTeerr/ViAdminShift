"""Brevity-suffix control (reviewer): the same absorbed T1np questions with and without "Chỉ trả lời ngắn gọn bằng tên,
không giải thích", plain system prompt (sys0) and today's date in it (sys1), reasoning off.

Per model and system prompt: old-only, new-first and both-maps rates (analyze_cue.label2), the share of answers that
mention the reform (sáp nhập / sắp xếp / 2025 / trước đây / nay là ...), and the median answer length, with the suffix
(the paper's runs) vs without it, on the same units. Output: results/analysis/nosuffix.json

  python3 scripts/score_nosuffix.py
"""
import glob
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(__file__))
from analyze_cue import label2  # noqa: E402
from minitest import load, nfc  # noqa: E402

S = "results/minitest/sysprompt"
REFORM = re.compile(r"sáp nhập|sắp xếp|2025|trước đây|trước kia|nay là|hiện nay thuộc|cũ|mới", re.I)


def stats(ps):
    labs = [label2(p) for p in ps]
    n = len(ps)
    return {"n": n,
            "old_only": sum(l == "outdated" for l in labs) / n,
            "new_first": sum(l in ("correct", "both_new") for l in labs) / n,
            "both": sum(l in ("both_new", "both_old") for l in labs) / n,
            "mentions_reform": sum(bool(REFORM.search(nfc(p.get("output") or ""))) for p in ps) / n,
            "median_chars": statistics.median(len(p.get("output") or "") for p in ps)}


def main():
    res = {}
    for f in sorted(glob.glob(f"{S}/preds_sys[01]ns_*.jsonl")):
        tag, rest = os.path.basename(f)[6:-6].split("_", 1)
        ns = {p["id"]: p for p in load(f) if p.get("absorbed")}
        ref = f"{S}/preds_{tag[:-2]}_{rest}.jsonl"
        if not os.path.exists(ref) or not ns:
            continue
        base = {p["id"]: p for p in load(ref) if p["id"] in ns}
        ids = sorted(set(ns) & set(base))
        if not ids:
            continue
        key = f"{rest}|{tag[:-2]}"
        res[key] = {"suffix": stats([base[i] for i in ids]), "no_suffix": stats([ns[i] for i in ids])}
        a, b = res[key]["suffix"], res[key]["no_suffix"]
        print(f"{key:40s} n={len(ids):3d}  old-only {100 * a['old_only']:3.0f} -> {100 * b['old_only']:3.0f}  "
              f"new-first {100 * a['new_first']:3.0f} -> {100 * b['new_first']:3.0f}  "
              f"both {100 * a['both']:3.0f} -> {100 * b['both']:3.0f}  "
              f"reform-mention {100 * a['mentions_reform']:3.0f} -> {100 * b['mentions_reform']:3.0f}  "
              f"chars {a['median_chars']:.0f} -> {b['median_chars']:.0f}")
    json.dump(res, open("results/analysis/nosuffix.json", "w"), indent=1)


if __name__ == "__main__":
    main()
