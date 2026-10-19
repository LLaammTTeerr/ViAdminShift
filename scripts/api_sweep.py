"""Run an item set on many OpenAI-compatible API models, reasoning off where the API allows it.

For each model, probe one item with each reasoning-off setting in order and keep the first that returns a non-empty
answer with finish_reason == "stop"; record the choice in <outdir>/settings.json, then run the full item set.
Usage: python3 scripts/api_sweep.py --items X.jsonl --url URL --api-key-env VAR --outdir DIR --tag cue3 model...
"""
import argparse
import concurrent.futures
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import minitest  # noqa: E402

OFF = [{"thinking": {"type": "disabled"}}, {"reasoning_effort": "minimal"}, {"reasoning_effort": "none"}, {}]


def pick(args, model, key, item):
    for extra in OFF:
        try:
            out, meta = minitest.chat(args.url, model, item["question"], args.max_tokens, api_key=key, extra=extra)
        except Exception as e:  # unsupported parameter -> try the next setting
            print(f"{model}: {json.dumps(extra)} -> {str(e)[:60]}", file=sys.stderr)
            continue
        if out.strip() and meta["finish"] == "stop":
            return extra, meta
    return None, None


def sweep(args, model, key, item, settings):
    extra, meta = pick(args, model, key, item)
    if extra is None:
        return model, "NO-SETTING"
    settings[model] = {"extra": extra, "probe": meta}
    out = os.path.join(args.outdir, f"preds_{args.tag}_{model}.jsonl")
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "minitest.py"), "run", "--items", args.items,
                        "--url", args.url, "--model", model, "--api-key-env", args.api_key_env, "--extra", json.dumps(extra),
                        "--max-tokens", str(args.max_tokens), "--par", str(args.par), "--out", out],
                       capture_output=True, text=True)
    return model, "ok" if r.returncode == 0 else "RUN-FAIL " + r.stderr[-300:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True); ap.add_argument("--url", required=True)
    ap.add_argument("--api-key-env", required=True); ap.add_argument("--outdir", required=True)
    ap.add_argument("--tag", required=True); ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--par", type=int, default=8); ap.add_argument("--models-par", type=int, default=4)
    ap.add_argument("models", nargs="+")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    key = os.environ[args.api_key_env]
    item = minitest.load(args.items)[0]
    path = os.path.join(args.outdir, "settings.json")
    settings = json.load(open(path)) if os.path.exists(path) else {}
    with concurrent.futures.ThreadPoolExecutor(args.models_par) as ex:
        for model, status in ex.map(lambda m: sweep(args, m, key, item, settings), args.models):
            print(f"{model}: {status}", flush=True)
            json.dump(settings, open(path, "w"), indent=1)


if __name__ == "__main__":
    main()
