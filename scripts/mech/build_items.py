"""Items for the steering / probing experiment on Muse-Glimmer (full precision).

T1np questions (ward, district; no province) for every T1 base of cue3full_items whose (ward, district) pair is unique
nationwide, under the six date-placement conditions of the paper (system prompt, question prefix). Split by base: 'derive' (direction estimation, 200 absorbed + 100 kept) and 'eval'
(the rest). The 80 T1np base units of the paper (cue3np_items) are kept in 'eval' so results compare to Table I.
"""
import collections
import json
import random
import sys

sys.path.insert(0, "scripts")
from minitest import CUES, SUFFIX, _cue, load, short  # noqa: E402

P = "data/processed"
OUT = "results/mech/items.jsonl"
S0 = "Bạn là một trợ lý hữu ích."
CONDS = {  # name: (system prompt, question prefix); same wording as scripts/vast/muse_controls.sh and muse_review.sh
    "sys0": (S0, ""),
    "sys1": (S0 + " Hôm nay là ngày 13/10/2026.", ""),
    "sysasof": (S0 + " Hãy trả lời theo thông tin tính đến tháng 10/2026.", ""),
    "sys0qm": (S0, "Hôm nay là ngày 13/10/2026. "),
    "sys0q": (S0, CUES["date"]),
    "sys2025": (S0 + " Hôm nay là ngày 01/01/2025.", ""),
}


def main():
    rows = {r["old_ward_code"]: r for r in load(f"{P}/ward_mapping.jsonl")
            if r["confidence"] == "high" and not r["is_partial"]}
    wd = collections.Counter((short(r["old_ward_name"]), short(r["old_district_name"])) for r in load(f"{P}/ward_mapping.jsonl"))
    paper = {it["base"].split("_", 1)[1] for it in load("results/minitest/items/cue3np_items.jsonl")}
    codes = sorted({it["base"].split("_", 1)[1] for it in load("results/minitest/items/cue3full_items.jsonl")
                    if it["qtype"].startswith("T1_")} | paper)
    bases = []
    for c in codes:
        r = rows.get(c)
        if r is None or wd[(short(r["old_ward_name"]), short(r["old_district_name"]))] != 1:
            continue
        absorbed = short(r["old_province_name"]) != short(r["new_province_name"])
        bases.append((c, absorbed, r))
    rng = random.Random(7)
    free = [b for b in bases if b[0] not in paper]
    rng.shuffle(free)
    derive = {b[0] for b in [b for b in free if b[1]][:200] + [b for b in free if not b[1]][:100]}
    n = collections.Counter()
    with open(OUT, "w", encoding="utf-8") as f:
        for c, absorbed, r in bases:
            split = "derive" if c in derive else "eval"
            q = f"{r['old_ward_name']}, {r['old_district_name']} thuộc tỉnh/thành phố nào?"
            for cue, (system, prefix) in CONDS.items():
                question = (prefix + q if prefix.startswith("Hôm") else _cue(prefix, q)) + SUFFIX
                f.write(json.dumps({"id": f"M_{c}__{cue}", "qtype": f"T1np_ward_province/{cue}", "absorbed": absorbed,
                                    "system": system, "question": question, "gold": [r["new_province_name"]],
                                    "old": [r["old_province_name"]] if absorbed else [], "cue": cue, "base": f"M_{c}",
                                    "split": split, "paper80": c in paper,
                                    "old_province": r["old_province_name"], "new_province": r["new_province_name"]},
                                   ensure_ascii=False) + "\n")
            n[(split, absorbed)] += 1
    print(dict(n), "paper80 kept:", sum(c in paper for c, _, _ in bases))


if __name__ == "__main__":
    main()
