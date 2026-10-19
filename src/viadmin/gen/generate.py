"""Generate the benchmark: ``uv run python -m viadmin.gen.generate``.

Writes (deterministic, seed 13):
  data/benchmark/items.jsonl              all items, qtypes interleaved (runner --limit is positional)
  data/benchmark/template_passages.jsonl  template + wiki-excerpt passages used by contexts
  data/benchmark/contexts.jsonl           {item_id, condition, passages, ...} for none/new/mixed
  data/benchmark/build_stats.json         counts (also used by docs/benchmark_report.md)
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter

from viadmin.eval.scorer import _make_targets, _match
from viadmin.eval.validate import lint_item
from viadmin.gen import contexts as ctxmod
from viadmin.gen import items as I
from viadmin.gen.common import BENCH, load_tables, nfc, rng_for, write_jsonl

QTYPE_ORDER = ["T0_headline", "T6_reverse", "T1_membership", "T1_newname", "T5_ward_successor",
               "T4_address", "T3_existence", "T2_composition"]


def _nfc_all(x):
    if isinstance(x, str):
        return nfc(x)
    if isinstance(x, list):
        return [_nfc_all(v) for v in x]
    if isinstance(x, dict):
        return {k: _nfc_all(v) for k, v in x.items()}
    return x


def _fix_indistinguishable_old(it: dict) -> None:
    """Short items: drop an old_answer the scorer would accept as correct (e.g. a unit-type
    change Thị trấn X -> Xã X, where the scorer strips the prefix)."""
    if it["format"] != "short" or it["old_answer"] is None:
        return
    gold = _make_targets([it["answer"], *it["answer_aliases"]])
    olds = it["old_answer"] if isinstance(it["old_answer"], list) else [it["old_answer"]]
    if any(_match(o, gold) for o in olds):
        it["meta"]["old_answer_dropped"] = it["old_answer"]
        it["old_answer"] = None


def build_groups(t) -> dict[str, list[list[dict]]]:
    c = I.Ctx(t)
    return {
        "T0_headline": I.build_t0(),
        "T6_reverse": I.build_t6(t),
        "T1_membership": I.build_t1(t, c),
        "T1_newname": I.build_t1n(t),
        "T5_ward_successor": I.build_t5(t, c),
        "T4_address": I.build_t4(t, c),
        "T3_existence": I.build_t3(t, c),
        "T2_composition": I.build_t2(t),
    }


def interleave(groups: dict[str, list[list[dict]]]) -> list[dict]:
    queues = {}
    for q in QTYPE_ORDER:
        lst = list(groups[q])
        rng_for(f"order:{q}").shuffle(lst)
        queues[q] = lst
    out: list[dict] = []
    while any(queues.values()):
        for q in QTYPE_ORDER:
            if queues[q]:
                out.extend(queues[q].pop(0))
    return out


def file_sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(BENCH))
    a = ap.parse_args(argv)
    from pathlib import Path
    out = Path(a.out)
    t = load_tables()
    groups = build_groups(t)
    items = interleave(groups)
    for it in items:
        _fix_indistinguishable_old(it)
    items = [_nfc_all(it) for it in items]
    # twins of T4 must remain lint-clean (diacritic-free collisions); drop a twin otherwise
    bad_twins = {it["id"] for it in items if it["meta"].get("has_diacritics") is False and lint_item(it)}
    if bad_twins:
        items = [it for it in items if it["id"] not in bad_twins]
        for it in items:
            if it["meta"].get("twin_id") and it["id"] + "-nd" in bad_twins:
                it["meta"]["twin_id"] = None
    passages, ctx_rows = ctxmod.build_contexts(t, items)
    write_jsonl(out / "items.jsonl", items)
    write_jsonl(out / "template_passages.jsonl", passages)
    write_jsonl(out / "contexts.jsonl", ctx_rows)
    stats = {
        "n_items": len(items),
        "by_qtype": dict(sorted(Counter(it["qtype"] for it in items).items())),
        "bad_twins_dropped": sorted(bad_twins),
        "sha256": {p: file_sha256(out / p) for p in ("items.jsonl", "template_passages.jsonl", "contexts.jsonl")},
    }
    (out / "build_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
