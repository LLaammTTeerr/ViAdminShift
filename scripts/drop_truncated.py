"""Move answers that stopped at the token limit out of a run's predictions.jsonl, so that the runner asks them again.

    uv run python scripts/drop_truncated.py results/bench/<model>
    MAX_MCQ=512 MAX_SHORT=512 bash scripts/bench_api.sh ...      # same arguments as the first run

The runner skips answered items, so the next pass sends exactly the removed prompts again (it refuses to resume if a
prompt would differ). The removed rows are appended to <out dir>/dropped_truncated.jsonl with the limits they were
generated with ("max_new_tokens", read from run_config.json) and without their scores, so the first answers stay on
record.
"""
import collections
import json
import sys
from pathlib import Path

KEEP = ("item_id", "condition", "model", "raw_output", "truncated", "prompt_sha1")


def record(p, limits):
    return json.dumps({**{k: p[k] for k in KEEP if k in p}, "max_new_tokens": limits}, ensure_ascii=False) + "\n"


def main():
    out = Path(sys.argv[1])
    preds = out / "predictions.jsonl"
    limits = json.loads((out / "run_config.json").read_text(encoding="utf-8"))["max_new_tokens"]
    rows = [l for l in preds.read_text(encoding="utf-8").splitlines(keepends=True) if l.strip()]
    keep, drop = [], []
    for l in rows:
        p = json.loads(l)
        (drop if p.get("truncated") else keep).append(p if p.get("truncated") else l)
    if not drop:
        print("no truncated answers")
        return 0
    with open(out / "dropped_truncated.jsonl", "a", encoding="utf-8") as f:
        for p in drop:
            f.write(record(p, limits))
    preds.write_text("".join(keep), encoding="utf-8")
    print(f"{len(rows)} -> {len(keep)}; removed {dict(collections.Counter(p['condition'] for p in drop))} "
          f"generated at {limits}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
