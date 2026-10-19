"""Activation probing and steering on Muse-Glimmer-30B (bf16, transformers, run on the vast instance).

Modes (all read results/mech/items.jsonl-format items):
  render  print the rendered prompt of one item (check that the chat template adds no date)
  acts    residual stream at the last prompt token, every decoder layer -> acts.pt {ids, layers x n x d (fp16)}
  gen     batched greedy generation; optional steering: add alpha * v[layer] at every position of one layer
  score   teacher-forced log-probabilities of every province name as the answer (new vs old map, no generation)
"""
import argparse
import json
import sys
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

M = "/workspace/hfmodels/Muse-Glimmer-30B"
SYS = "You are a helpful AI assistant."  # any system message replaces the template's default block (today's date)


def load_items(path, split=None, cue=None, limit=None):
    its = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    its = [i for i in its if (split is None or i["split"] == split) and (cue is None or i["cue"] == cue)]
    return its[:limit] if limit else its


def render(tok, it):
    msgs = [{"role": "system", "content": it.get("system", SYS)}, {"role": "user", "content": it["question"]}]
    return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, reasoning_strength="none")


def load_model():
    tok = AutoTokenizer.from_pretrained(M)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(M, dtype=torch.bfloat16, device_map="auto").eval()
    layers = max((m for n, m in model.named_modules() if isinstance(m, torch.nn.ModuleList) and n.endswith("layers")),
                 key=len)
    return tok, model, layers


def first_device(model):
    return next(model.parameters()).device


class Steer:
    """Adds alpha * v to the output hidden state of one decoder layer, at every position."""

    def __init__(self, layer, v, alpha):
        self.v, self.alpha = v, alpha
        self.h = layer.register_forward_hook(self.hook)

    def hook(self, mod, inp, out):
        hs = out[0] if isinstance(out, tuple) else out
        hs = hs + self.alpha * self.v.to(hs.device, hs.dtype)
        return (hs,) + tuple(out[1:]) if isinstance(out, tuple) else hs

    def remove(self):
        self.h.remove()


def cmd_render(a):
    tok = AutoTokenizer.from_pretrained(M)
    it = load_items(a.items, limit=1)[0]
    print(render(tok, it))


def cmd_acts(a):
    tok, model, layers = load_model()
    items = load_items(a.items, a.split, a.cue)
    store = [[] for _ in layers]
    hooks = []
    for i, l in enumerate(layers):
        def hook(mod, inp, out, i=i):
            hs = out[0] if isinstance(out, tuple) else out
            store[i].append(hs[:, -1, :].float().cpu().half())
        hooks.append(l.register_forward_hook(hook))
    t0 = time.time()
    for s in range(0, len(items), a.batch):
        b = items[s:s + a.batch]
        enc = tok([render(tok, it) for it in b], return_tensors="pt", padding=True,
                  add_special_tokens=False).to(first_device(model))
        with torch.no_grad():
            model(**enc)
        print(f"acts {s + len(b)}/{len(items)} {time.time() - t0:.0f}s", file=sys.stderr, flush=True)
    for h in hooks:
        h.remove()
    torch.save({"ids": [it["id"] for it in items], "acts": torch.stack([torch.cat(x) for x in store])}, a.out)


def cmd_gen(a):
    tok, model, layers = load_model()
    items = load_items(a.items, a.split, a.cue, a.limit)
    runs = [(None, 0.0, "base")]
    if a.vec:
        v_all = torch.load(a.vec)  # {"diff": layers x d}
        for spec in a.steer:  # "layer:alpha[:random]"
            parts = spec.split(":")
            L, alpha = int(parts[0]), float(parts[1])
            v = v_all["diff"][L].float()
            if len(parts) > 2 and parts[2] == "random":
                g = torch.Generator().manual_seed(int(parts[3]) if len(parts) > 3 else 0)
                r = torch.randn(v.shape, generator=g)
                v = r / r.norm() * v.norm()
            runs.append((L, alpha, spec))
            runs[-1] = (L, alpha, spec, v)
        if a.no_base:
            runs = runs[1:]
    t0 = time.time()
    with open(a.out, "a", encoding="utf-8") as f:
        for run in runs:
            st = Steer(layers[run[0]], run[3], run[1]) if run[0] is not None else None
            for s in range(0, len(items), a.batch):
                b = items[s:s + a.batch]
                enc = tok([render(tok, it) for it in b], return_tensors="pt", padding=True,
                          add_special_tokens=False).to(first_device(model))
                with torch.no_grad():
                    out = model.generate(**enc, max_new_tokens=a.max_tokens, do_sample=False, pad_token_id=tok.pad_token_id)
                texts = tok.batch_decode(out[:, enc["input_ids"].shape[1]:], skip_special_tokens=True)
                for it, t in zip(b, texts):
                    f.write(json.dumps({**{k: v for k, v in it.items() if k != "question"}, "output": t,
                                        "steer": run[2]}, ensure_ascii=False) + "\n")
                f.flush()
                print(f"gen {run[2]} {s + len(b)}/{len(items)} {time.time() - t0:.0f}s", file=sys.stderr, flush=True)
            if st:
                st.remove()


def cmd_score(a):
    """log P(answer = name | prompt) for the gold (new) and old province names, plus the rank of each among all names."""
    tok, model, layers = load_model()
    items = load_items(a.items, a.split, a.cue, a.limit)
    names = sorted({json.loads(l)["name"] for f in ("provinces_new", "provinces_old")
                    for l in open(f"{f}.jsonl", encoding="utf-8")})
    short = [n.replace("Thành phố ", "").replace("Tỉnh ", "") for n in names]
    t0 = time.time()
    with open(a.out, "w", encoding="utf-8") as f:
        for k, it in enumerate(items):
            p = render(tok, it)
            pids = tok(p, add_special_tokens=False)["input_ids"]
            seqs = [pids + tok(s, add_special_tokens=False)["input_ids"] for s in short]
            lp = []
            for s in range(0, len(seqs), a.batch):
                b = seqs[s:s + a.batch]
                m = max(map(len, b))
                ids = torch.tensor([[tok.pad_token_id] * (m - len(x)) + x for x in b], device=first_device(model))
                att = (torch.arange(m, device=ids.device)[None, :] >= torch.tensor([m - len(x) for x in b], device=ids.device)[:, None]).long()
                with torch.no_grad():
                    logits = model(input_ids=ids, attention_mask=att).logits.float().log_softmax(-1)
                for j, x in enumerate(b):
                    n_ans = len(x) - len(pids)
                    tgt = ids[j, m - n_ans:]
                    lp.append(logits[j, m - n_ans - 1:m - 1].gather(-1, tgt[:, None]).sum().item())
            score = dict(zip(names, lp))
            order = sorted(names, key=lambda n: -score[n])
            rec = {"id": it["id"], "absorbed": it["absorbed"], "cue": it["cue"],
                   "new": it["new_province"], "old": it["old_province"],
                   "lp_new": score.get(it["new_province"]), "lp_old": score.get(it["old_province"]),
                   "rank_new": order.index(it["new_province"]) + 1 if it["new_province"] in score else None,
                   "rank_old": order.index(it["old_province"]) + 1 if it["old_province"] in score else None,
                   "top": order[:3]}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if k % 20 == 0:
                print(f"score {k}/{len(items)} {time.time() - t0:.0f}s", file=sys.stderr, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["render", "acts", "gen", "score"])
    ap.add_argument("--items", default="items.jsonl")
    ap.add_argument("--split")
    ap.add_argument("--cue")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--max-tokens", type=int, default=24)
    ap.add_argument("--vec")
    ap.add_argument("--steer", nargs="*", default=[])
    ap.add_argument("--no-base", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    {"render": cmd_render, "acts": cmd_acts, "gen": cmd_gen, "score": cmd_score}[a.mode](a)


if __name__ == "__main__":
    main()
