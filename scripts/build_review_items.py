"""Items for the second-review controls.

    newname : T1 with the POST-reform ward name and no district ("Phường Gò Công thuộc tỉnh/thành phố nào?"), 240 units x
              none/date/reform. The question presupposes no pre-reform unit, so an old answer cannot be frame-following.
              `old` is set only where the name also existed before the reform in another province (old_answer_province).
    prefix  : every T1 / T1np base of cue3 + cue3np with two extra prefixes: "Hiện nay, " (currently) and a
              content-free filler of similar length ("Cho tôi hỏi một câu, ").

    python3 scripts/build_review_items.py
"""
import json
import sys

sys.path.insert(0, "scripts")
from minitest import SUFFIX, CUES, _cue  # noqa: E402

I = "results/minitest/items"
PREFIX = {"now": "Hiện nay, ", "filler": "Cho tôi hỏi một câu, "}


def load(p):
    return [json.loads(l) for l in open(p)]


def main():
    old_prov = {p["code"]: p["name"] for p in load("data/processed/provinces_old.jsonl")}
    out = []
    for it in load("data/benchmark/items.jsonl"):
        m = it.get("meta", {})
        if it["qtype"] != "T1_newname" or m.get("cue") != "none":
            continue
        q = it["question"].replace(" thuộc tỉnh/thành phố nào?", "")
        oc = m.get("old_answer_province")
        old = [old_prov[oc]] if oc and old_prov.get(oc) and old_prov[oc] != m["new_province_name"] else []
        base = it["id"].split("__")[0]
        for cue, pre in CUES.items():
            out.append({"id": f"{base}__{cue}", "depth": "newname", "qtype": f"T1new_ward_province/{cue}",
                        "absorbed": bool(old), "question": _cue(pre, q + " thuộc tỉnh/thành phố nào?") + SUFFIX,
                        "gold": [m["new_province_name"]], "old": old, "cue": cue, "base": base})
    with open(f"{I}/newname_items.jsonl", "w") as f:
        f.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in out)
    print("newname", len(out), "absorbed bases", sum(x["absorbed"] for x in out) // 3)

    out = []
    for src in ("cue3_items", "cue3np_items"):
        for it in load(f"{I}/{src}.jsonl"):
            if it["cue"] != "none" or not it["qtype"].startswith("T1"):
                continue
            q = it["question"][: -len(SUFFIX)]
            for cue, pre in PREFIX.items():
                out.append({**it, "id": f"{it['base']}__{cue}", "qtype": it["qtype"].replace("/none", f"/{cue}"),
                            "question": _cue(pre, q) + SUFFIX, "cue": cue})
    with open(f"{I}/prefix_items.jsonl", "w") as f:
        f.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in out)
    print("prefix", len(out))


if __name__ == "__main__":
    main()
