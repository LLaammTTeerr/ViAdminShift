"""Quick closed-book mini-test of surface / compose / deep knowledge of the 2025 reform.

Stdlib only, so it runs on the lab servers against any OpenAI-compatible endpoint (llama-server).

  python3 scripts/minitest.py build --processed data/processed --probe data/probe --out minitest_items.jsonl
  python3 scripts/minitest.py run --items minitest_items.jsonl --url http://127.0.0.1:8080 --model NAME --out preds.jsonl
  python3 scripts/minitest.py score preds1.jsonl preds2.jsonl ...
"""
import argparse
import concurrent.futures
import os
import collections
import json
import random
import re
import sys
import threading
import time
import unicodedata
import urllib.request
import urllib.error

PREFIXES = ["thành phố", "tp.", "tp ", "tỉnh", "phường", "xã", "thị trấn", "đặc khu", "quận", "huyện", "thị xã"]
ALIASES = {"hồ chí minh": ["hcm", "sài gòn - gia định"], "huế": ["thừa thiên huế", "thừa thiên - huế"]}
SUFFIX = " Chỉ trả lời ngắn gọn bằng tên, không giải thích."


def nfc(s):
    return unicodedata.normalize("NFC", s or "")


def norm(s):
    s = nfc(s).lower()
    s = re.sub(r"[\"'`*().,;:!?]", " ", s)
    for p in PREFIXES:
        s = re.sub(r"(^|\s)" + re.escape(p.strip()) + r"(?=\s)", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def short(name):
    """'Tỉnh Bình Dương' -> 'Bình Dương'."""
    return norm(name)


# Old/new-style tone placement ('Hoà' = 'Hòa', 'Uý' = 'Úy'), as viadmin.eval.normalize.canon_tone_placement.
_TONE_MAP = {f + unicodedata.normalize("NFC", s + t): unicodedata.normalize("NFC", f + t) + s
             for f, s in (("o", "a"), ("o", "e"), ("u", "y")) for t in ("\u0300", "\u0301", "\u0309", "\u0303", "\u0323")}
_TONE_RE = re.compile("|".join(map(re.escape, _TONE_MAP)))
_DASH_RE = re.compile(r"\s*[-\u2010-\u2015\u2212]\s*")


def snorm(s):
    """norm() for scoring: also canonical tone placement and one form of dash ('Bà Rịa – Vũng Tàu' = 'Bà Rịa-Vũng Tàu'
    = 'Bà Rịa - Vũng Tàu'). Item building keeps norm(), so the committed item files rebuild unchanged."""
    s = _TONE_RE.sub(lambda m: _TONE_MAP[m.group(0)], norm(s))
    return re.sub(r"\s+", " ", _DASH_RE.sub(" - ", s)).strip()


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def build(args):
    rng = random.Random(13)
    P = args.processed
    old_prov = {p["code"]: p for p in load(f"{P}/provinces_old.jsonl")}
    new_prov = {p["code"]: p for p in load(f"{P}/provinces_new.jsonl")}
    rows = [r for r in load(f"{P}/ward_mapping.jsonl") if r["confidence"] == "high"]
    items = []

    for h in load(f"{args.probe}/headline_probe.jsonl"):
        items.append({"id": "H_" + h["id"], "depth": "surface", "qtype": "T0_headline", "question": h["question"],
                      "gold": [h["answer"]] + h.get("answer_aliases", []),
                      "old": (h["old_answer"] if isinstance(h.get("old_answer"), list) else [h["old_answer"]]) if h.get("old_answer") else [],
                      "numeric": h["answer"].isdigit()})

    # T6: old province -> new province
    old_to_new = collections.defaultdict(set)
    for r in rows:
        old_to_new[r["old_province_code"]].add(r["new_province_code"])
    for oc, p in sorted(old_prov.items()):
        if len(old_to_new[oc]) != 1:
            continue
        nc = next(iter(old_to_new[oc]))
        gold, old = new_prov[nc]["name"], p["name"]
        absorbed = short(gold) != short(old)
        items.append({"id": f"T6_{oc}", "depth": "surface", "qtype": "T6_reverse", "absorbed": absorbed,
                      "question": f"Sau đợt sắp xếp đơn vị hành chính năm 2025, địa bàn {p['name']} trước đây "
                                  f"hiện nay thuộc tỉnh/thành phố nào của Việt Nam?" + SUFFIX,
                      "gold": [gold], "old": [old] if absorbed else [], "group": oc})

    absorbed_codes = {i["group"] for i in items if i.get("absorbed")}

    # cue factor: same province fact without the reform cue
    for it in [i for i in items if i["qtype"] == "T6_reverse"]:
        p = old_prov[it["group"]]
        items.append({**it, "id": it["id"] + "_nocue", "qtype": "T6_reverse_nocue",
                      "question": f"Hiện nay, địa bàn {p['name']} trước đây thuộc tỉnh/thành phố nào của Việt Nam?" + SUFFIX})

    # compose: ward in an absorbed old province, old province named
    whole = [r for r in rows if not r["is_partial"] and r["old_province_code"] in absorbed_codes]
    for r in rng.sample(whole, 40):
        items.append({"id": f"C_{r['old_ward_code']}", "depth": "compose", "qtype": "T1_membership",
                      "question": f"Hiện nay, {r['old_ward_name']} (trước đây thuộc {r['old_district_name']}, "
                                  f"{r['old_province_name']}) thuộc tỉnh/thành phố nào?" + SUFFIX,
                      "gold": [r["new_province_name"]], "old": [r["old_province_name"]], "group": r["old_province_code"]})
        items.append({"id": f"C_{r['old_ward_code']}_cue", "depth": "compose", "qtype": "T1_membership_cue",
                      "question": f"Sau đợt sắp xếp đơn vị hành chính năm 2025, {r['old_ward_name']} (trước đây thuộc "
                                  f"{r['old_district_name']}, {r['old_province_name']}) hiện nay thuộc tỉnh/thành phố nào?" + SUFFIX,
                      "gold": [r["new_province_name"]], "old": [r["old_province_name"]], "group": r["old_province_code"]})

    # deep 1: new ward name (unique nationwide) -> new province
    new_wards = load(f"{P}/wards_new.jsonl")
    cnt = collections.Counter(short(w["name"]) for w in new_wards)
    old_names = collections.defaultdict(set)
    for r in rows:
        old_names[short(r["old_ward_name"])].add(r["old_province_code"])
    uniq = [w for w in new_wards if cnt[short(w["name"])] == 1]
    for w in rng.sample(uniq, 40):
        olds = old_names.get(short(w["name"]), set())
        old_ans = [old_prov[c]["name"] for c in olds if short(old_prov[c]["name"]) != short(new_prov[w["province_code"]]["name"])]
        items.append({"id": f"N_{w['code']}", "depth": "deep", "qtype": "T1_newname",
                      "question": f"{w['name']} là đơn vị hành chính cấp xã (sau ngày 1/7/2025). "
                                  f"Đơn vị này thuộc tỉnh/thành phố nào?" + SUFFIX,
                      "gold": [new_prov[w["province_code"]]["name"]], "old": old_ans[:1]})

    # deep 2: old ward -> successor new ward (name changed, not divided)
    succ = [r for r in rows if not r["is_partial"] and r["change_type"] in ("merged", "renamed")
            and short(r["old_ward_name"]) != short(r["new_ward_name"])]
    for r in rng.sample(succ, 30):
        items.append({"id": f"S_{r['old_ward_code']}", "depth": "deep", "qtype": "T5_ward_successor",
                      "question": f"Sau đợt sắp xếp đơn vị hành chính năm 2025, {r['old_ward_name']} "
                                  f"({r['old_district_name']}, {r['old_province_name']} cũ) nay thuộc "
                                  f"xã/phường mới nào?" + SUFFIX,
                      "gold": [r["new_ward_name"]], "old": [r["old_ward_name"]]})

    with open(args.out, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(collections.Counter((i["depth"], i["qtype"]) for i in items), file=sys.stderr)


CUES = {"none": "", "date": "Tính đến tháng 10/2026, ", "reform": "Sau đợt sắp xếp đơn vị hành chính năm 2025, "}


def _cue(prefix, q):
    return prefix + (q[0].lower() + q[1:] if prefix and not q.startswith(("Xã", "Phường", "Thị trấn")) else q)


def build_cue3(args):
    """Clean 3-level cue ladder (none/date/reform); 'none' has no temporal or change markers."""
    rng = random.Random(31)
    P = args.processed
    old_prov = {p["code"]: p for p in load(f"{P}/provinces_old.jsonl")}
    new_prov = {p["code"]: p for p in load(f"{P}/provinces_new.jsonl")}
    rows = [r for r in load(f"{P}/ward_mapping.jsonl") if r["confidence"] == "high" and not r["is_partial"]]
    o2n = collections.defaultdict(set)
    for r in rows:
        o2n[r["old_province_code"]].add(r["new_province_code"])
    bases = []
    for oc, p in sorted(old_prov.items()):
        if len(o2n[oc]) != 1 or args.no_province:
            continue
        g = new_prov[next(iter(o2n[oc]))]["name"]
        absorbed = short(g) != short(p["name"])
        bases.append((f"P_{oc}", "surface", "T6_province", f"Địa bàn {p['name']} thuộc đơn vị hành chính cấp tỉnh nào?",
                      [g], [p["name"]] if absorbed else [], absorbed))
    absorbed_rows = [r for r in rows if short(r["old_province_name"]) != short(r["new_province_name"])]
    kept_rows = [r for r in rows if short(r["old_province_name"]) == short(r["new_province_name"])]
    # (ward, district) pairs that name a unique old ward nationwide: needed when the province is omitted
    wd = collections.Counter((short(r["old_ward_name"]), short(r["old_district_name"])) for r in load(f"{P}/ward_mapping.jsonl"))
    for r in rng.sample(absorbed_rows, args.n_absorbed) + rng.sample(kept_rows, args.n_kept):
        absorbed = short(r["old_province_name"]) != short(r["new_province_name"])
        if args.no_province:  # robustness: the old province is not in the question, so it cannot be copied
            if wd[(short(r["old_ward_name"]), short(r["old_district_name"]))] == 1:
                bases.append((f"N_{r['old_ward_code']}", "compose", "T1np_ward_province",
                              f"{r['old_ward_name']}, {r['old_district_name']} thuộc tỉnh/thành phố nào?",
                              [r["new_province_name"]], [r["old_province_name"]] if absorbed else [], absorbed))
            continue
        bases.append((f"W_{r['old_ward_code']}", "compose", "T1_ward_province",
                      f"{r['old_ward_name']}, {r['old_district_name']}, {r['old_province_name']} thuộc tỉnh/thành phố nào?",
                      [r["new_province_name"]], [r["old_province_name"]] if absorbed else [], absorbed))
    # deep level: old ward -> current ward; control = wards that kept their name
    # drop wards whose new name is lexically in the question (e.g. new "Xã Chư Sê" from old "Huyện Chư Sê")
    leak = lambda r: f" {short(r['new_ward_name'])} " in " " + " ".join(
        short(r[k]) for k in ("old_ward_name", "old_district_name", "old_province_name")) + " "
    renamed = [r for r in rows if short(r["old_ward_name"]) != short(r["new_ward_name"]) and not leak(r)]
    same = [r for r in rows if short(r["old_ward_name"]) == short(r["new_ward_name"])]
    n_same = min(len(same), args.n_successor // 2)
    for r in rng.sample(renamed, args.n_successor) + rng.sample(same, n_same):
        absorbed = short(r["old_ward_name"]) != short(r["new_ward_name"])
        bases.append((f"S_{r['old_ward_code']}", "deep", "T5_ward_successor",
                      f"Khu vực {r['old_ward_name']} ({r['old_district_name']}, {r['old_province_name']}) "
                      f"thuộc đơn vị hành chính cấp xã nào?",
                      [r["new_ward_name"]], [r["old_ward_name"]] if absorbed else [], absorbed))
    items = []
    for bid, depth, qt, q, gold, old, absorbed in bases:
        for cue, prefix in CUES.items():
            items.append({"id": f"{bid}__{cue}", "depth": depth, "qtype": f"{qt}/{cue}", "absorbed": absorbed,
                          "question": _cue(prefix, q) + SUFFIX, "gold": gold, "old": old, "cue": cue, "base": bid})
    with open(args.out, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(collections.Counter((i["qtype"], i["absorbed"]) for i in items), file=sys.stderr)


RAG_INSTR = ("Dựa vào các tài liệu dưới đây, hãy trả lời câu hỏi.\n\n{docs}\n\nCâu hỏi: {q}")


def build_rag(args):
    """Template-passage conflict test on compose + ward-successor items.

    Conditions: new (new passage only), mixed_on / mixed_no (old+new, old first / new first, no dates),
    dated_on / dated_no (same, each passage stamped with its update date)."""
    rng = random.Random(29)
    P = args.processed
    rows = [r for r in load(f"{P}/ward_mapping.jsonl") if r["confidence"] == "high" and not r["is_partial"]]
    absorbed = [r for r in rows if r["province_changed"] and short(r["old_province_name"]) != short(r["new_province_name"])
                and r["change_type"] in ("merged", "renamed") and short(r["old_ward_name"]) != short(r["new_ward_name"])]
    picked = rng.sample(absorbed, args.n)
    items = []
    for r in picked:
        x, d, p, y, q = r["old_ward_name"], r["old_district_name"], r["old_province_name"], r["new_ward_name"], r["new_province_name"]
        old_doc = f"{x} là một đơn vị hành chính cấp xã thuộc {d}, {p}, Việt Nam."
        new_doc = f"{y} là một đơn vị hành chính cấp xã thuộc {q}, Việt Nam. Địa bàn {y} bao gồm toàn bộ khu vực của {x}."
        qs = {
            "T1_compose": (f"Hiện nay, khu vực {x} (trước đây thuộc {d}) thuộc tỉnh/thành phố nào?", [q], [p]),
            "T5_successor": (f"Hiện nay, khu vực {x} ({d}) thuộc đơn vị hành chính cấp xã nào?", [y], [x]),
        }
        stamp_old, stamp_new = "[Tài liệu cập nhật ngày 15/03/2023]", "[Tài liệu cập nhật ngày 20/08/2025]"
        conds = {
            "new": [new_doc],
            "mixed_on": [old_doc, new_doc], "mixed_no": [new_doc, old_doc],
            "dated_on": [f"{stamp_old} {old_doc}", f"{stamp_new} {new_doc}"],
            "dated_no": [f"{stamp_new} {new_doc}", f"{stamp_old} {old_doc}"],
        }
        for qt, (qtext, gold, old) in qs.items():
            for cond, docs in conds.items():
                body = "\n".join(f"Tài liệu {i + 1}: {t}" for i, t in enumerate(docs))
                items.append({"id": f"R_{r['old_ward_code']}_{qt}_{cond}", "depth": cond, "qtype": qt,
                              "question": RAG_INSTR.format(docs=body, q=qtext) + SUFFIX, "gold": gold, "old": old})
    with open(args.out, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(len(items), "rag items", file=sys.stderr)


def run_hf(args):
    """Batched greedy generation with transformers on a local GPU (4-bit if --4bit)."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    tok = AutoTokenizer.from_pretrained(args.model)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    kw = {"dtype": torch.float16, "device_map": "cuda"}
    if args.four_bit:
        kw["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                                       bnb_4bit_compute_dtype=torch.float16)
    model = AutoModelForCausalLM.from_pretrained(args.model, **kw).eval()
    items = load(args.items)
    name = args.model.split("/")[-1] + ("-nf4" if args.four_bit else "")
    t0 = time.time()
    with open(args.out, "w", encoding="utf-8") as f:
        for s in range(0, len(items), args.batch):
            batch = items[s:s + args.batch]
            prompts = []
            for it in batch:
                msgs = [{"role": "user", "content": it["question"]}]
                try:
                    prompts.append(tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False))
                except TypeError:
                    prompts.append(tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True))
            enc = tok(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
            with torch.no_grad():
                out = model.generate(**enc, max_new_tokens=args.max_tokens, do_sample=False, pad_token_id=tok.pad_token_id)
            texts = tok.batch_decode(out[:, enc["input_ids"].shape[1]:], skip_special_tokens=True)
            for it, t in zip(batch, texts):
                f.write(json.dumps({"id": it["id"], "model": name, "output": t, **{k: it[k] for k in it if k != "question"}},
                                   ensure_ascii=False) + "\n")
            print(f"{name} {s + len(batch)}/{len(items)} {time.time() - t0:.0f}s", file=sys.stderr, flush=True)


def chat(url, model, question, max_tokens, api_key=None, extra=None, system=None):
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": question}]
    body = {"model": model, "messages": msgs, "temperature": 0,
            "max_tokens": max_tokens}
    body.update(extra if extra is not None else {"chat_template_kwargs": {"enable_thinking": False}})
    body = {k: v for k, v in body.items() if v is not None}  # extra {"temperature": null} drops a field
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    req = urllib.request.Request(url + "/v1/chat/completions", data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.load(r)
    c = d["choices"][0]
    meta = {"finish": c.get("finish_reason"), "ctoks": (d.get("usage") or {}).get("completion_tokens"),
            "reasoned": bool(c["message"].get("reasoning_content") or c["message"].get("reasoning"))}
    return (c["message"].get("content") or ""), meta


def run(args):
    items = load(args.items)
    done = set()
    try:
        done = {p["id"] for p in load(args.out)}
    except FileNotFoundError:
        pass
    todo = [it for it in items if it["id"] not in done]
    if args.only:  # "QTYPE[:absorbed[:CUE]]", e.g. "T1_ward_province:absorbed:reform"
        qt, ab, cue = (args.only.split(":") + ["", ""])[:3]
        todo = [it for it in todo if it["qtype"].startswith(qt + "/") and (not ab or it.get("absorbed"))
                and (not cue or it.get("cue") == cue)]
    key = os.environ.get(args.api_key_env) if args.api_key_env else None
    extra = json.loads(args.extra) if args.extra else None
    t0 = time.time()

    lock, slot = threading.Lock(), [0.0]

    def throttle():  # at most args.rpm requests per minute across threads
        if not args.rpm:
            return
        with lock:
            wait = slot[0] - time.time()
            slot[0] = max(slot[0], time.time()) + 60 / args.rpm
        if wait > 0:
            time.sleep(wait)

    def one(it):
        for attempt in range(8):
            throttle()
            try:
                return it, *chat(args.url, args.model, it["question"], args.max_tokens, api_key=key, extra=extra, system=args.system)
            except urllib.error.HTTPError as e:
                if e.code not in (429, 500, 502, 503, 504, 529) or attempt == 7:
                    raise
                time.sleep(min(2 ** attempt * 5, 120))
            except (TimeoutError, urllib.error.URLError, ConnectionError):
                if attempt == 7:
                    raise
                time.sleep(10)

    with open(args.out, "a", encoding="utf-8") as f, concurrent.futures.ThreadPoolExecutor(args.par) as ex:
        for i, (it, out, meta) in enumerate(ex.map(one, todo)):
            f.write(json.dumps({"id": it["id"], "model": args.model, "output": out, **meta,
                                **{k: it[k] for k in it if k != "question"}},
                               ensure_ascii=False) + "\n")
            f.flush()
            if i % 50 == 0:
                print(f"{args.model} {i}/{len(todo)} {time.time() - t0:.0f}s", file=sys.stderr, flush=True)


NUM = re.compile(r"\d[\d.,]*")


def label(p):
    out = re.sub(r"<think>.*?</think>", " ", nfc(p["output"]), flags=re.S)
    if p.get("numeric"):
        nums = {n.replace(".", "").replace(",", "") for n in NUM.findall(out)}
        g = {snorm(x).replace(".", "") for x in p["gold"]}
        o = {snorm(x).replace(".", "") for x in p["old"]}
        hit_g, hit_o = bool(nums & g) or any(x in snorm(out) for x in g if not x.isdigit()), bool(nums & o) or any(x in snorm(out) for x in o if not x.isdigit())
    else:
        n = " " + snorm(out) + " "
        def has(names):
            cands = set()
            for x in names:
                cands.add(snorm(x))
                cands.update(ALIASES.get(short(x), []))
            return any(c and f" {c} " in n for c in cands)
        hit_g, hit_o = has(p["gold"]), has(p["old"])
    if hit_g and not hit_o:
        return "correct"
    if hit_o and not hit_g:
        return "outdated"
    if hit_g and hit_o:
        return "both"
    return "other"


def knows(args):
    """Exit 0 iff the model 'knows the update' (pre-registered: absorbed ward items, cue=reform, correct >= 0.50)."""
    allp = load(args.preds)
    empty = sum(not (p.get("output") or "").strip() for p in allp) / max(len(allp), 1)
    if empty > 0.2:  # e.g. a reasoning model spent max_tokens thinking: a measurement failure, not "doesn't know"
        print(f"{args.preds}: {empty:.0%} empty outputs -- INVALID run, not a knowledge result")
        sys.exit(2)
    ps = [p for p in allp if p["qtype"] == "T1_ward_province/reform" and p.get("absorbed")]
    acc = sum(label(p) == "correct" for p in ps) / max(len(ps), 1)
    print(f"{args.preds}: reform/absorbed correct {acc:.2f} (n={len(ps)})")
    sys.exit(0 if ps and acc >= args.threshold else 1)


def score(args):
    by = collections.defaultdict(collections.Counter)
    for path in args.preds:
        for p in load(path):
            key = (p["model"], p["depth"], p["qtype"] + ("" if "absorbed" not in p else ("/absorbed" if p.get("absorbed") else "/kept")))
            by[key][label(p)] += 1
    print(f"{'model':28} {'depth':8} {'qtype':22} {'n':>4} {'correct':>8} {'outdated':>9} {'both':>5} {'other':>6}")
    for k in sorted(by):
        c = by[k]
        n = sum(c.values())
        print(f"{k[0][:28]:28} {k[1]:8} {k[2]:22} {n:4} {c['correct']/n:8.2f} {c['outdated']/n:9.2f} {c['both']/n:5.2f} {c['other']/n:6.2f}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("--processed", default="data/processed"); b.add_argument("--probe", default="data/probe"); b.add_argument("--out", required=True)
    r = sub.add_parser("run"); r.add_argument("--items", required=True); r.add_argument("--url", default="http://127.0.0.1:8080"); r.add_argument("--model", required=True); r.add_argument("--out", required=True); r.add_argument("--max-tokens", type=int, default=40)
    r.add_argument("--par", type=int, default=1, help="concurrent requests")
    r.add_argument("--rpm", type=float, default=0, help="max requests per minute (0: no limit)")
    r.add_argument("--only", default=None, help="QTYPE[:absorbed]: run only these items")
    r.add_argument("--api-key-env", default=None); r.add_argument("--extra", default=None, help="JSON merged into the request body (replaces enable_thinking kwargs)")
    r.add_argument("--system", default=None, help="system prompt (default: none)")
    s = sub.add_parser("score"); s.add_argument("preds", nargs="+")
    k = sub.add_parser("knows"); k.add_argument("preds"); k.add_argument("--threshold", type=float, default=0.5)
    c3 = sub.add_parser("build-cue3"); c3.add_argument("--processed", default="data/processed"); c3.add_argument("--out", required=True)
    c3.add_argument("--n-absorbed", type=int, default=80); c3.add_argument("--n-kept", type=int, default=40)
    c3.add_argument("--n-successor", type=int, default=0, help="T5 renamed wards (+ half as many unchanged controls)")
    c3.add_argument("--no-province", action="store_true", help="T1 only, address without the old province (same sampled wards)")
    br = sub.add_parser("build-rag"); br.add_argument("--processed", default="data/processed"); br.add_argument("--n", type=int, default=40); br.add_argument("--out", required=True)
    h = sub.add_parser("run-hf"); h.add_argument("--items", required=True); h.add_argument("--model", required=True); h.add_argument("--out", required=True)
    h.add_argument("--max-tokens", type=int, default=32); h.add_argument("--batch", type=int, default=16); h.add_argument("--four-bit", action="store_true")
    a = ap.parse_args()
    {"build": build, "run": run, "score": score, "build-rag": build_rag, "run-hf": run_hf, "build-cue3": build_cue3, "knows": knows}[a.cmd](a)


if __name__ == "__main__":
    main()
