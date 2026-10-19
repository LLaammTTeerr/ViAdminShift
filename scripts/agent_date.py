"""How an agent receives the date: system prompt, question, earlier turn, or a get_current_date tool (DeepSeek API).

T1np items (ward, district; no province) from results/mech/items.jsonl: the paper's 80 absorbed + 40 kept units plus
280 absorbed + 80 kept others (seeded). Each base is asked under every condition below; the same date (13/10/2026).

  python3 scripts/agent_date.py run [MODEL]   # resumes; results/minitest/agent/preds_agent_<short>.jsonl
  python3 scripts/agent_date.py score         # -> results/analysis/agent_date.json, agent_date_table.tex
  python3 scripts/agent_date.py rewrite       # query rewriter (DeepSeek, reasoning off) -> rewrites.jsonl
MODEL is a key of MODELS (default deepseek-flash, DeepSeek API; the others through OpenRouter, reasoning off).
Run flags: --paper (the paper's 80 + 40 units only), --ext (paper units + the first 220 absorbed / 40 kept others:
300 absorbed in all), --conds a,b (only these conditions), --think (reasoning on; preds_agent_<short>__think.jsonl),
--rpm N.
"""
import collections
import concurrent.futures
import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request

sys.path.insert(0, "scripts")
from analyze_cue import label2  # noqa: E402
from minitest import CUES, SUFFIX, _cue, load  # noqa: E402

MODELS = {  # short name: (base url, key env, model id, extra body)
    "deepseek-flash": ("https://api.deepseek.com", "DS_TOKEN", "deepseek-flash", {"thinking": {"type": "disabled"}}),
    "gpt-6-sol": ("https://openrouter.ai/api", "OPENROUTER_TOKEN", "openai/gpt-6-sol", {"reasoning": {"enabled": False}}),
    "kimi-k3": ("https://openrouter.ai/api", "OPENROUTER_TOKEN", "moonshotai/kimi-k3", {"reasoning": {"enabled": False}}),
    "gpt-6-luna": ("https://openrouter.ai/api", "OPENROUTER_TOKEN", "openai/gpt-6-luna", {"reasoning": {"enabled": False}}),
    "gpt-5.6-terra": ("https://openrouter.ai/api", "OPENROUTER_TOKEN", "openai/gpt-5.6-terra", {"reasoning": {"enabled": False}}),
    "hy4-preview": ("https://openrouter.ai/api", "OPENROUTER_TOKEN", "tencent/hy4-preview", {"reasoning": {"enabled": False}}),
}
LABEL = {"deepseek-flash": "DS", "gpt-6-sol": "G6", "kimi-k3": "Kimi", "gpt-6-luna": "Luna", "gpt-5.6-terra": "Terra",
         "hy4-preview": "HY4"}  # table header abbreviations, spelled out in the caption
URL, KEY_ENV, MODEL, EXTRA = MODELS["deepseek-flash"]
SHORT = "deepseek-flash"
PAPER_ONLY = False  # --paper: only the paper's 80 absorbed + 40 kept units
EXT = False  # --ext: paper units + 220 absorbed / 40 kept others (n=300 absorbed)
CONDS = None  # --conds: run only these conditions
THINK = False  # --think: reasoning on
MAX_TOKENS = 256
RPM = 0  # --rpm N: at most N requests per minute (OpenRouter new-account limit is 20 per model)
_lock, _slot = threading.Lock(), [0.0]


def out_path(short, think=False):
    return f"results/minitest/agent/preds_agent_{short}{'__think' if think else ''}.jsonl"


REWRITES_PATH = "results/minitest/agent/rewrites_deepseek-flash.jsonl"
REWRITER = ("Bạn là bộ viết lại truy vấn cho một trợ lý AI. Hôm nay là ngày {today}. Hãy viết lại câu hỏi của người "
            "dùng cho rõ ràng và đầy đủ để trợ lý trả lời chính xác theo thông tin hiện hành. Chỉ trả về câu hỏi đã viết "
            "lại, không trả lời câu hỏi.")  # you rewrite queries for an AI assistant; today is ...; rewrite the question
# clearly and completely so the assistant answers correctly with current information; return only the question
REWRITES = {}
S0 = "Bạn là một trợ lý hữu ích."
TODAY_VI, TODAY_ISO = "13/10/2026", "2026-10-13"
TOOL = {"type": "function", "function": {"name": "get_current_date", "description": "Trả về ngày hiện tại (YYYY-MM-DD).",
                                         "parameters": {"type": "object", "properties": {}}}}
CALL = {"role": "assistant", "content": "",
        "tool_calls": [{"id": "call_0", "type": "function", "function": {"name": "get_current_date", "arguments": "{}"}}]}
RESULT = {"role": "tool", "tool_call_id": "call_0", "content": TODAY_ISO}
INSTR = S0 + " Khi câu hỏi phụ thuộc vào thời điểm hiện tại, hãy gọi công cụ get_current_date trước khi trả lời."


def conds(q, base=None):
    """condition -> (messages, tools). q is the plain question with the answer-format suffix."""
    sys0 = {"role": "system", "content": S0}
    u = {"role": "user", "content": q}
    extra = {}
    if base in REWRITES:  # the rewriter's question, answer-format suffix appended
        extra["rewrite"] = ([sys0, {"role": "user", "content": REWRITES[base].strip() + SUFFIX}], None)
    return {**extra,
        "sysasof": ([{"role": "system", "content": S0 + " Hãy trả lời theo thông tin tính đến tháng 10/2026."}, u], None),
        "sys0": ([sys0, u], None),
        "sys1": ([{"role": "system", "content": f"{S0} Hôm nay là ngày {TODAY_VI}."}, u], None),
        "sys0qm": ([sys0, {"role": "user", "content": f"Hôm nay là ngày {TODAY_VI}. " + q}], None),
        "sys0q": ([sys0, {"role": "user", "content": _cue(CUES["date"], q[:-len(SUFFIX)]) + SUFFIX}], None),
        "history": ([sys0, {"role": "user", "content": "Hôm nay là ngày bao nhiêu?"},
                     {"role": "assistant", "content": f"Hôm nay là ngày {TODAY_VI}."}, u], None),
        "tool_result": ([sys0, u, CALL, RESULT], [TOOL]),
        "tool_offer": ([sys0, u], [TOOL]),
        "tool_instr": ([{"role": "system", "content": INSTR}, u], [TOOL]),
    }


def items():
    its = [i for i in load("results/mech/items.jsonl") if i["cue"] == "sys0"]
    paper = [i for i in its if i["paper80"]]
    if PAPER_ONLY:
        return paper
    rng = random.Random(11)
    rest_a = [i for i in its if not i["paper80"] and i["absorbed"]]
    rest_k = [i for i in its if not i["paper80"] and not i["absorbed"]]
    a, k = rng.sample(rest_a, 280), rng.sample(rest_k, 80)
    if EXT:
        return paper + a[:220] + k[:40]
    return paper + a + k


def post(messages, tools):
    body = {"model": MODEL, "messages": messages, "temperature": 0, "max_tokens": MAX_TOKENS, **EXTRA}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(URL + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + os.environ[KEY_ENV]})
    for attempt in range(8):
        if RPM:
            with _lock:
                wait = _slot[0] - time.time()
                _slot[0] = max(_slot[0], time.time()) + 60 / RPM
            if wait > 0:
                time.sleep(wait)
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                j = json.load(r)
                m = j["choices"][0]["message"]
                m["_ctoks"] = (j.get("usage") or {}).get("completion_tokens")
                m["_reasoned"] = bool(m.get("reasoning") or m.get("reasoning_content")) or bool(
                    ((j.get("usage") or {}).get("completion_tokens_details") or {}).get("reasoning_tokens"))
                return m
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 7:
                raise
            time.sleep(min(2 ** attempt * 5, 120))
        except (TimeoutError, urllib.error.URLError, ConnectionError):
            if attempt == 7:
                raise
            time.sleep(10)


def ask(messages, tools):
    """One answer; if the model calls get_current_date, return the date and ask again (at most twice)."""
    called, rsn = 0, False
    msgs = list(messages)
    for _ in range(3):
        m = post(msgs, tools)
        rsn = rsn or m["_reasoned"]
        tcs = m.get("tool_calls") or []
        if not tcs:
            return m.get("content") or "", called, rsn
        called += 1
        msgs.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": tcs})
        msgs += [{"role": "tool", "tool_call_id": tc["id"], "content": TODAY_ISO} for tc in tcs]
    return "", called, rsn


def load_rewrites():
    if os.path.exists(REWRITES_PATH):
        REWRITES.update({r["base"]: r["rewrite"] for r in load(REWRITES_PATH)})


def rewrite():
    """Date-aware query rewriting with DeepSeek (reasoning off), on the paper's 80 + 40 units."""
    global URL, KEY_ENV, MODEL, EXTRA, PAPER_ONLY
    URL, KEY_ENV, MODEL, EXTRA = MODELS["deepseek-flash"]
    PAPER_ONLY = True
    load_rewrites()
    todo = [it for it in items() if it["base"] not in REWRITES]
    sysm = {"role": "system", "content": REWRITER.format(today=TODAY_VI)}

    def one(it):
        q = it["question"][:-len(SUFFIX)]
        m = post([sysm, {"role": "user", "content": q}], None)
        return {"base": it["base"], "question": q, "rewrite": (m.get("content") or "").strip()}

    with open(REWRITES_PATH, "a", encoding="utf-8") as f, concurrent.futures.ThreadPoolExecutor(8) as ex:
        for rec in ex.map(one, todo):
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def run():
    load_rewrites()
    OUT = out_path(SHORT, THINK)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    done = {p["id"] for p in load(OUT)} if os.path.exists(OUT) else set()
    todo = []
    for it in items():
        for c, (msgs, tools) in conds(it["question"], it["base"]).items():
            if CONDS and c not in CONDS:
                continue
            pid = f"{it['base']}__{c}"
            if pid not in done:
                todo.append((it, c, pid, msgs, tools))
    print(f"{len(todo)} to run", file=sys.stderr)

    def one(x):
        it, c, pid, msgs, tools = x
        out, called, rsn = ask(msgs, tools)
        return {"id": pid, "model": MODEL, "cond": c, "output": out, "tool_calls": called, "reasoned": rsn,
                **{k: it[k] for k in ("base", "absorbed", "gold", "old", "paper80")}}

    t0 = time.time()
    with open(OUT, "a", encoding="utf-8") as f, concurrent.futures.ThreadPoolExecutor(8) as ex:
        for k, rec in enumerate(ex.map(one, todo)):
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if k % 200 == 0:
                print(f"{k}/{len(todo)} {time.time() - t0:.0f}s", file=sys.stderr, flush=True)


ORDER = ["sys0", "sys1", "sysasof", "sys0qm", "sys0q", "history", "tool_result", "tool_offer", "tool_instr"]


def boot(by_base, a, b, key, B=2000, seed=0):
    d = [v[a][key] - v[b][key] for v in by_base.values() if a in v and b in v]
    rng = random.Random(seed)
    ms = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(B))
    return {"delta": sum(d) / len(d), "lo": ms[int(0.025 * B)], "hi": ms[int(0.975 * B)], "n": len(d)}


def score_model(ps):
    res = {}
    for grp, sel in (("absorbed", True), ("kept", False)):
        by_c = collections.defaultdict(list)
        by_base = collections.defaultdict(dict)
        for p in ps:
            if p["absorbed"] != sel:
                continue
            l = label2(p)
            v = {"nf": float(l in ("correct", "both_new")), "oo": float(l == "outdated"), "called": float(p["tool_calls"] > 0)}
            by_c[p["cond"]].append(v)
            by_base[p["base"]][p["cond"]] = v
        r = {}
        for c, vs in by_c.items():
            n = len(vs)
            r[c] = {"n": n, "new_first": sum(v["nf"] for v in vs) / n, "old_only": sum(v["oo"] for v in vs) / n,
                    "tool_call_rate": sum(v["called"] for v in vs) / n}
            if sel and c != "sys1" and "sys1" in by_c:
                r[c]["d_old_only_vs_sys1"] = boot(by_base, c, "sys1", "oo")
        if sel:  # outcome when the model did / did not call the offered tool
            for c in ("tool_offer", "tool_instr"):
                for flag in (True, False):
                    vs = [by_base[b][c] for b in by_base if c in by_base[b] and (by_base[b][c]["called"] > 0) == flag]
                    if vs and c in r:
                        r[c]["called" if flag else "not_called"] = {
                            "n": len(vs), "new_first": sum(v["nf"] for v in vs) / len(vs),
                            "old_only": sum(v["oo"] for v in vs) / len(vs)}
        res[grp] = r
    return res


def score():
    res = {}
    paper = {}
    for short in MODELS:
        if os.path.exists(out_path(short)):
            ps = load(out_path(short))
            res[short] = score_model(ps)
            paper[short] = score_model([p for p in ps if p["paper80"]])  # same 80 + 40 units for every model
        if os.path.exists(out_path(short, True)):  # reasoning on (--think); the paper's units only
            LABEL[short + "|think"] = LABEL[short] + r"$^r$"
            paper[short + "|think"] = score_model(load(out_path(short, True)))
    res = {"all": res, "paper80": paper}
    os.makedirs("results/analysis", exist_ok=True)
    json.dump(res, open("results/analysis/agent_date.json", "w"), indent=1, ensure_ascii=False)
    tex(paper)
    for short, rm in res["all"].items():
        for grp, r in rm.items():
            print(short, grp)
            for c in ORDER:
                if c in r:
                    x = r[c]
                    d = x.get("d_old_only_vs_sys1")
                    print(f"  {c:12s} n={x['n']:4d} new-first {100 * x['new_first']:5.1f} old-only {100 * x['old_only']:5.1f}"
                          f" tool {100 * x['tool_call_rate']:5.1f}"
                          + (f"  d_oo vs sys1 {100 * d['delta']:+.0f} [{100 * d['lo']:+.0f},{100 * d['hi']:+.0f}]" if d else "")
                          + "".join(f"  {k}: n={x[k]['n']} nf {100 * x[k]['new_first']:.0f} oo {100 * x[k]['old_only']:.0f}"
                                    for k in ("called", "not_called") if k in x))


def score_round2():
    """n=300 placement (paper units + 220 others, reasoning off), query rewriting, reasoning-on agent conditions."""
    global EXT, PAPER_ONLY
    EXT, PAPER_ONLY = True, False
    ext = {it["base"] for it in items()}
    EXT = False
    rw = {r["base"]: r for r in load(REWRITES_PATH)} if os.path.exists(REWRITES_PATH) else {}
    out = {"n300": {}, "rewrite": {}, "think": {}}
    for short in MODELS:
        if not os.path.exists(out_path(short)):
            continue
        ps = [p for p in load(out_path(short)) if p["base"] in ext]
        r = score_model(ps)["absorbed"]
        if all(c in r for c in ("sys1", "sys0q", "sys0qm", "sysasof")):
            out["n300"][short] = {c: r[c] for c in ("sys1", "sys0q", "sys0qm", "sysasof")}
        pp = score_model([p for p in load(out_path(short)) if p["paper80"]])
        if "rewrite" in pp["absorbed"]:
            out["rewrite"][short] = {g: {c: pp[g][c] for c in ("sys1", "sys0q", "rewrite") if c in pp[g]} for g in pp}
        if os.path.exists(out_path(short, True)):
            out["think"][short] = score_model(load(out_path(short, True)))
    if rw:  # what the rewriter did to the 80 absorbed questions
        meta = {it["base"]: it for it in load("results/mech/items.jsonl") if it["cue"] == "sys0" and it["paper80"]}
        sh = lambda n: n.replace("Thành phố ", "").replace("Tỉnh ", "")
        ab = [b for b in rw if meta.get(b, {}).get("absorbed")]
        has = lambda b, pat: pat.lower() in rw[b]["rewrite"].lower()
        out["rewriter"] = {
            "n": len(ab),
            "date_or_present": sum(any(has(b, t) for t in ("2026", "hiện hành", "hiện nay", "hiện tại", "tính đến", "mới nhất"))
                                   for b in ab) / len(ab),
            "names_old_province": sum(has(b, sh(meta[b]["old_province"])) for b in ab) / len(ab),
            "names_new_province": sum(has(b, sh(meta[b]["new_province"])) for b in ab) / len(ab)}
    json.dump(out, open("results/analysis/round2.json", "w"), indent=1, ensure_ascii=False)
    tex_round2(out)
    if os.path.exists("results/analysis/agent_date.json"):  # agent table with the reasoning-on column(s) added
        res = json.load(open("results/analysis/agent_date.json"))["paper80"]
        for m, r in out["think"].items():
            LABEL[m + "|think"] = LABEL[m] + r"$^r$"
            res[m + "|think"] = r
        tex(res)
    for k, v in out["n300"].items():
        print("n300", k, {c: f"{100 * x['old_only']:.0f}" + (f" d{100 * x['d_old_only_vs_sys1']['delta']:+.0f}[{100 * x['d_old_only_vs_sys1']['lo']:+.0f},{100 * x['d_old_only_vs_sys1']['hi']:+.0f}]" if 'd_old_only_vs_sys1' in x else "") + f" n={x['n']}" for c, x in v.items()})
    for k, v in out["rewrite"].items():
        print("rewrite", k, {g: {c: f"{100 * x['new_first']:.0f}/{100 * x['old_only']:.0f}" for c, x in vv.items()} for g, vv in v.items()})
    for k, v in out["think"].items():
        print("think-agent", k, {c: f"{100 * x['old_only']:.0f} ({100 * x['tool_call_rate']:.0f})" for c, x in v["absorbed"].items()})
    print("rewriter", out.get("rewriter"))


ROWS = [("sys0", "no date"), ("tool_offer", "tool offered"), ("tool_instr", "tool offered + instruction"),
        ("tool_result", "tool result in context"), ("history", "earlier turn"),
        ("sys1", "system: ``today is''"), ("sys0qm", "question: ``today is''"), ("sys0q", "question: ``as of''")]


def tex_round2(out, path="results/analysis/round2_table.tex"):
    """Reasoning off. Left: old-only (%) on 300 absorbed T1np units per placement/phrasing; right: the paper's 80
    absorbed units with the date in the system prompt vs a question rewritten by DeepSeek, and kept units correct."""
    ms = [m for m in MODELS if m in out["n300"] and m in out["rewrite"]]
    pc = lambda x: f"{100 * x:.0f}"
    rows = [r"\begin{tabular}{@{}l cccc ccc@{}}", r"\toprule",
            r" & \multicolumn{4}{c}{300 units: old-only} & \multicolumn{3}{c}{rewriting (80 + 40 kept)} \\",
            r"\cmidrule(lr){2-5}\cmidrule(lr){6-8}",
            r"Model & sys today & Q today & Q as of & sys as of & sys today & rewritten & kept \\", r"\midrule"]
    for m in ms:
        a, w = out["n300"][m], out["rewrite"][m]
        rows.append(f"{LABEL[m]} & " + " & ".join(pc(a[c]["old_only"]) for c in ("sys1", "sys0qm", "sys0q", "sysasof"))
                    + f" & {pc(w['absorbed']['sys1']['old_only'])} & {pc(w['absorbed']['rewrite']['old_only'])}"
                    + f" & {pc(w['kept']['rewrite']['new_first'])} \\\\")
    rows += [r"\bottomrule", r"\end{tabular}"]
    open(path, "w").write("\n".join(rows) + "\n")


def tex(res, out="results/analysis/agent_date_table.tex"):
    """Old-only (%) on the paper's 80 absorbed T1np units per condition and model; tool rows add the call rate."""
    ms = [m for m in MODELS if m in res] + [m for m in res if m.endswith("|think")]
    rows = [r"\begin{tabular}{@{}l" + "c" * len(ms) + r"@{}}", r"\toprule",
            "Date given as & " + " & ".join(LABEL[m] for m in ms) + r" \\", r"\midrule"]
    for c, what in ROWS:
        cells = []
        for m in ms:
            x = res[m]["absorbed"].get(c)
            if x is None:
                cells.append("--")
                continue
            cell = f"{100 * x['old_only']:.0f}"
            if c in ("tool_offer", "tool_instr"):
                cell += f" ({100 * x['tool_call_rate']:.0f})"
            cells.append(cell)
        rows.append(what + " & " + " & ".join(cells) + r" \\")
    rows += [r"\bottomrule", r"\end{tabular}"]
    open(out, "w").write("\n".join(rows) + "\n")


if __name__ == "__main__":
    if sys.argv[1] == "run" and len(sys.argv) > 2:
        SHORT = sys.argv[2]
        URL, KEY_ENV, MODEL, EXTRA = MODELS[SHORT]
        PAPER_ONLY = "--paper" in sys.argv
        EXT = "--ext" in sys.argv
        if "--rpm" in sys.argv:
            RPM = float(sys.argv[sys.argv.index("--rpm") + 1])
        if "--conds" in sys.argv:
            CONDS = set(sys.argv[sys.argv.index("--conds") + 1].split(","))
        if "--think" in sys.argv:
            THINK, MAX_TOKENS = True, 8192
            EXTRA = {**EXTRA, "reasoning": {"enabled": True}} if "reasoning" in EXTRA else {**EXTRA, "thinking": {"type": "enabled"}}
    {"run": run, "score": score, "rewrite": rewrite, "score2": score_round2}[sys.argv[1]]()
