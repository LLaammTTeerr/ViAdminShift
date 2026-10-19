"""Evaluation runner CLI.

Example::

  uv run python -m viadmin.eval.runner --backend hf --model Qwen/Qwen3-1.7B \\
      --items data/benchmark/items.jsonl --contexts data/benchmark/contexts.jsonl \\
      --passages data/wiki/passages.jsonl \\
      --conditions closed,rag_new,rag_mixed --limit 50 --out results/qwen3-1.7b_smoke

Resumable: (item_id, condition) pairs already in predictions.jsonl are skipped, but only
if their stored ``prompt_sha1`` equals the prompt that would be sent now (same items,
--today, --passage-fields, PROMPT_VERSION...); otherwise the run stops (use another --out).
``--rescore`` relabels existing raw outputs with the current scorer (no generation).
Predictions whose item_id is not in the items file are kept untouched (never deleted) and
counted as ``n_unscored_predictions`` in scores.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Callable

from viadmin.eval.metrics import aggregate
from viadmin.eval.prompts import PROMPT_VERSION, DEFAULT_TODAY, Condition, build_messages, parse_condition
from viadmin.eval.scorer import score

DEFAULT_PASSAGE_FILES = ("data/wiki/passages.jsonl", "data/benchmark/template_passages.jsonl")
DEFAULT_MAX_NEW = {"mcq": 16, "short": 64}


# --------------------------------------------------------------------------- io


def read_jsonl(path: str | os.PathLike) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_passages(paths: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in paths:
        if not Path(p).exists():
            continue
        for row in read_jsonl(p):
            pid = row["passage_id"]
            if pid in out and out[pid] != row:
                raise ValueError(f"passage_id {pid!r} defined differently in two passage files")
            out[pid] = row
    return out


def load_contexts(path: str | None) -> dict[tuple[str, str], list[str]]:
    if not path or not Path(path).exists():
        return {}
    out: dict[tuple[str, str], list[str]] = {}
    for row in read_jsonl(path):
        key = (row["item_id"], row["condition"])
        if key in out:
            raise ValueError(f"duplicate context row for {key}")
        out[key] = list(row.get("passages") or [])
    return out


def resolve_passages(
    item_id: str, cond: Condition, contexts: dict, passages: dict[str, dict]
) -> list[dict]:
    if cond.base == "closed":
        return []
    key = (item_id, cond.context_condition)
    if key not in contexts:
        raise KeyError(f"no context row for item {item_id!r} condition {cond.context_condition!r}")
    missing = [p for p in contexts[key] if p not in passages]
    if missing:
        raise KeyError(f"item {item_id!r}: passage ids not found in passage files: {missing}")
    return [passages[p] for p in contexts[key]]


# --------------------------------------------------------------------------- core


def score_row(item: dict, row: dict) -> dict:
    r = score(item, row.get("raw_output"))
    row.update(parsed=r.parsed, label=r.label, match_detail=r.match_detail, correct_nodiac=r.correct_nodiac,
               label_nodiac=r.label_nodiac, label_strict=r.label_strict)
    if r.components is not None:  # T4 per-component labels (ward / province)
        row["components"] = r.components
    return row


def prompt_sha1(msgs: list[dict]) -> str:
    return hashlib.sha1(json.dumps(msgs, ensure_ascii=False).encode()).hexdigest()[:12]


def write_scores(out_dir: Path, items_by_id: dict[str, dict],
                 log: Callable[[str], None] = lambda s: print(s, file=sys.stderr)) -> dict:
    preds_path = out_dir / "predictions.jsonl"
    preds = read_jsonl(preds_path) if preds_path.exists() else []
    scores = aggregate(preds, items_by_id)
    if scores.get("n_unscored_predictions"):
        log(f"[runner] WARNING: {scores['n_unscored_predictions']} prediction(s) have item ids not in the "
            f"items file; they are kept in predictions.jsonl but excluded from scores.json")
    (out_dir / "scores.json").write_text(json.dumps(scores, ensure_ascii=False, indent=2), encoding="utf-8")
    return scores


def rescore(out_dir: Path, items_by_id: dict[str, dict],
            log: Callable[[str], None] = lambda s: print(s, file=sys.stderr)) -> dict:
    """Relabel every stored prediction whose item is known; rows of unknown items are
    written back unchanged (a filtered run must never delete other predictions)."""
    preds_path = out_dir / "predictions.jsonl"
    rows = read_jsonl(preds_path)
    rows = [score_row(items_by_id[r["item_id"]], r) if r["item_id"] in items_by_id else r for r in rows]
    tmp = preds_path.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(preds_path)
    return write_scores(out_dir, items_by_id, log)


def run(
    backend,
    items: list[dict],
    conditions: list[str],
    out_dir: str | os.PathLike,
    contexts: dict | None = None,
    passages: dict | None = None,
    batch_size: int = 32,
    max_new_tokens: dict[str, int] | None = None,
    today: date = DEFAULT_TODAY,
    passage_fields: tuple[str, ...] = ("text",),
    run_config: dict | None = None,
    log: Callable[[str], None] = lambda s: print(s, file=sys.stderr),
    score_items: list[dict] | None = None,
) -> dict:
    """Generate the pending (item, condition) pairs, then rescore ALL stored predictions
    against ``score_items`` (the full items file; defaults to ``items``)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    contexts, passages = contexts or {}, passages or {}
    max_new = {**DEFAULT_MAX_NEW, **(max_new_tokens or {})}
    conds = [parse_condition(c) for c in conditions]
    items_by_id = {it["id"]: it for it in items}
    if len(items_by_id) != len(items):
        raise ValueError("duplicate item ids")

    all_items_by_id = dict(items_by_id)
    for it in score_items or []:
        all_items_by_id.setdefault(it["id"], it)

    preds_path = out / "predictions.jsonl"
    done: dict[tuple[str, str], str | None] = {}
    if preds_path.exists():
        for r in read_jsonl(preds_path):
            if r.get("model") != backend.name:
                raise SystemExit(
                    f"{preds_path} contains predictions from model {r.get('model')!r}, "
                    f"refusing to mix with {backend.name!r}; use another --out"
                )
            done[(r["item_id"], r["condition"])] = r.get("prompt_sha1")

    # Build all pending jobs first so missing contexts fail before any GPU time is spent,
    # and check that resumed pairs were generated from the identical prompt.
    jobs: dict[tuple[str, str], list[tuple[dict, Condition, list[dict]]]] = defaultdict(list)
    stale: list[str] = []
    for cond in conds:
        for it in items:
            key = (it["id"], cond.name)
            msgs = build_messages(it, cond, resolve_passages(it["id"], cond, contexts, passages),
                                  today=today, passage_fields=passage_fields)
            if key in done:
                if done[key] is not None and done[key] != prompt_sha1(msgs):
                    stale.append(f"{key[0]}|{key[1]}")
                continue
            jobs[(cond.name, it["format"])].append((it, cond, msgs))
    if stale:
        raise SystemExit(
            f"{len(stale)} stored prediction(s) in {preds_path} were generated from a different prompt "
            f"than this run would send (changed items, --today, --passage-fields, contexts or "
            f"PROMPT_VERSION), e.g. {stale[:3]}; refusing to resume. Use another --out."
        )

    cfg = {
        **(run_config or {}),
        "backend": backend.info(),
        "conditions": conditions,
        "prompt_version": PROMPT_VERSION,
        "today": today.isoformat(),
        "passage_fields": list(passage_fields),
        "max_new_tokens": max_new,
        "n_items": len(items),
    }
    # run_config.json describes the latest invocation; earlier ones are kept in
    # "previous_runs" (oldest first) so resumed directories stay fully documented.
    cfg_path = out / "run_config.json"
    history: list[dict] = []
    if cfg_path.exists():
        try:
            prev = json.loads(cfg_path.read_text(encoding="utf-8"))
            history = list(prev.pop("previous_runs", [])) + [prev]
        except (json.JSONDecodeError, AttributeError):
            history = []
    cfg["previous_runs"] = history
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    n_total = sum(len(v) for v in jobs.values())
    log(f"[runner] {len(done)} done, {n_total} pending, model={backend.name}")
    n_new, t0 = 0, time.time()
    with open(preds_path, "a", encoding="utf-8") as f:
        for (cname, fmt), js in jobs.items():
            for s in range(0, len(js), batch_size):
                chunk = js[s : s + batch_size]
                outs = backend.generate([m for _, _, m in chunk], max_new[fmt])
                trunc = getattr(backend, "last_truncated", None) or [False] * len(outs)
                for (it, cond, msgs), raw, tr in zip(chunk, outs, trunc):
                    row = {
                        "item_id": it["id"],
                        "condition": cond.name,
                        "model": backend.name,
                        "raw_output": raw,
                        "truncated": bool(tr),
                        "prompt_sha1": prompt_sha1(msgs),
                    }
                    score_row(it, row)
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                n_new += len(chunk)
                el = time.time() - t0
                log(f"[runner] {cname}/{fmt}: {n_new}/{n_total} ({n_new / max(el, 1e-9):.2f} items/s)")
    # Relabel everything (incl. rows from earlier resumed sessions and from items outside
    # this run's --qtypes/--limit filter) with the current scorer.
    return rescore(out, all_items_by_id, log)


# --------------------------------------------------------------------------- CLI


def _rel(arg):
    """Paths inside the working directory as relative paths (comma lists too), so run_config.json carries no local
    directory names."""
    if not isinstance(arg, str):
        return arg
    cwd = os.getcwd() + os.sep
    return ",".join(x[len(cwd):] if x.startswith(cwd) else x for x in arg.split(","))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", choices=["hf", "vllm", "openai"], default="hf")
    ap.add_argument("--model", required=False)
    ap.add_argument("--items", default="data/benchmark/items.jsonl")
    ap.add_argument("--contexts", default="data/benchmark/contexts.jsonl")
    ap.add_argument("--passages", default=",".join(DEFAULT_PASSAGE_FILES),
                    help="comma-separated passage files (missing files are skipped)")
    ap.add_argument("--conditions", default="closed")
    ap.add_argument("--passage-fields", default="text",
                    help="comma-separated passage fields used as passage body, e.g. text,admin_text")
    ap.add_argument("--qtypes", default=None, help="comma-separated qtype filter")
    ap.add_argument("--limit", type=int, default=None, help="first N items (after --qtypes filter)")
    ap.add_argument("--out", required=False)
    ap.add_argument("--batch-size", type=int, default=32, help="items per backend.generate call")
    ap.add_argument("--max-new-mcq", type=int, default=DEFAULT_MAX_NEW["mcq"])
    ap.add_argument("--max-new-short", type=int, default=DEFAULT_MAX_NEW["short"])
    ap.add_argument("--today", default=DEFAULT_TODAY.isoformat(), help="date for +sysdate (YYYY-MM-DD)")
    ap.add_argument("--enable-thinking", action="store_true", help="(not recommended) keep Qwen3 thinking on")
    # hf
    ap.add_argument("--quant", choices=["none", "4bit"], default="none")
    ap.add_argument("--dtype", default="bfloat16")
    ap.add_argument("--hf-batch-size", type=int, default=8)
    # vllm
    ap.add_argument("--max-model-len", type=int, default=8192)
    ap.add_argument("--gpu-mem", type=float, default=0.9)
    ap.add_argument("--tp", type=int, default=1)
    # openai
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--api-key-env", default="OPENAI_API_KEY")
    ap.add_argument("--template-kwargs", action="store_true",
                    help="send chat_template_kwargs.enable_thinking (vLLM/SGLang servers)")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--extra-body", default=None,
                    help='JSON merged into every request body, e.g. \'{"thinking": {"type": "disabled"}}\' (DeepSeek)')
    # modes
    ap.add_argument("--rescore", action="store_true", help="relabel existing predictions, no generation")
    ap.add_argument("--validate", action="store_true", help="lint items and exit")
    a = ap.parse_args(argv)

    if a.validate:
        from viadmin.eval.validate import lint_file

        probs = lint_file(a.items)
        for p in probs:
            print(p)
        print(f"{len(probs)} problem(s)", file=sys.stderr)
        return 1 if probs else 0

    if not a.out:
        ap.error("--out is required")
    items = read_jsonl(a.items)
    all_items = list(items)
    items_by_id = {it["id"]: it for it in items}

    if a.rescore:
        s = rescore(Path(a.out), items_by_id)
        print(json.dumps({c: v["all"]["accuracy"] for c, v in s["by_condition"].items()}, indent=1))
        return 0

    if not a.model:
        ap.error("--model is required")
    if a.qtypes:
        keep = set(a.qtypes.split(","))
        items = [it for it in items if it["qtype"] in keep]
    if a.limit:
        items = items[: a.limit]

    conditions = [c.strip() for c in a.conditions.split(",") if c.strip()]
    for c in conditions:
        parse_condition(c)  # fail fast
    contexts = load_contexts(a.contexts)
    passages = load_passages([p for p in a.passages.split(",") if p])

    from viadmin.eval.backends import make_backend

    think = a.enable_thinking
    if a.backend == "hf":
        be = make_backend("hf", a.model, quant=a.quant, dtype=a.dtype, batch_size=a.hf_batch_size,
                          enable_thinking=think)
    elif a.backend == "vllm":
        be = make_backend("vllm", a.model, enable_thinking=think, max_model_len=a.max_model_len,
                          gpu_memory_utilization=a.gpu_mem, tensor_parallel_size=a.tp)
    else:
        be = make_backend("openai", a.model, base_url=a.base_url, api_key_env=a.api_key_env,
                          template_kwargs=a.template_kwargs, enable_thinking=think, concurrency=a.concurrency,
                          extra_body=json.loads(a.extra_body) if a.extra_body else None)

    s = run(
        be, items, conditions, a.out, contexts=contexts, passages=passages, batch_size=a.batch_size,
        max_new_tokens={"mcq": a.max_new_mcq, "short": a.max_new_short},
        today=date.fromisoformat(a.today),
        passage_fields=tuple(x for x in a.passage_fields.split(",") if x),
        run_config={"items": _rel(a.items), "contexts": _rel(a.contexts), "passages": _rel(a.passages),
                    "limit": a.limit, "qtypes": a.qtypes, "argv": ["viadmin.eval.runner", *map(_rel, sys.argv[1:])]},
        score_items=all_items,
    )
    print(json.dumps({c: v["all"] for c, v in s["by_condition"].items()}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
