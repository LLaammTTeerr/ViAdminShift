"""Validate the generated benchmark: ``uv run python -m viadmin.gen.validate [data/benchmark]``.

Checks (each returns a list of problems; the CLI prints them and exits 1 if any):
* schema of every item (SPEC fields + meta keys), NFC text, unique ids, eval linter clean
* MCQ: 4 choices, answer letter in range, old_answer letter != answer, choice order identical
  across the cue variants of one cue_group
* short: old_answer differs from the answer
* cue rules: the three variants exist, share gold/choices, and the cue=none wording has no
  temporal/change marker outside the entity names
* no answer leakage: a gold name that CHANGED (new province, new ward) does not occur with its
  unit prefix in the question
* gold provenance: every ward-level gold agrees with ward_mapping (confidence high)
* T3 balance (exists vs not), MCQ letter balance per qtype
* contexts: none/new/mixed rows for every item, passage ids resolvable, new contains the gold
  names (must_contain re-verified), mixed = 1 old-era + the same new passage, the old passage
  contains the old answer when it changed, total length <= 2,500 chars
* T4 twins: the no-diacritic twin has the same gold and an address without diacritics
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from viadmin.eval.normalize import normalize_text, strip_diacritics
from viadmin.eval.validate import lint_item
from viadmin.gen.common import BENCH, WIKI, key, load_jsonl, load_tables, lower_prefix, short_of
from viadmin.gen.contexts import has_name, wn

REQ = ("id", "qtype", "question", "format", "choices", "answer", "answer_aliases", "old_answer", "meta")
REQ_META = ("province_changed", "ward_changed", "change_type", "old_province_code", "new_province_code",
            "old_ward_code", "new_ward_code", "consistency_group", "has_diacritics", "depth", "cue", "cue_group")
CUE_QTYPES = {"T6_reverse", "T1_membership", "T1_newname", "T5_ward_successor"}
CUE_MARKERS = re.compile(r"(?<!\w)(trước đây|cũ|mới|nay|hiện nay|hiện|sau sắp xếp|sắp xếp|sáp nhập|2025|2026|tính đến)(?!\w)")
MAX_CTX = 2500


def _is_nfc(x) -> bool:
    if isinstance(x, str):
        return unicodedata.is_normalized("NFC", x)
    if isinstance(x, list):
        return all(_is_nfc(v) for v in x)
    if isinstance(x, dict):
        return all(_is_nfc(v) for v in x.values())
    return True


def gold_text(it: dict) -> str:
    if it["format"] == "mcq":
        return it["choices"]["ABCD".index(it["answer"])]
    return it["answer"]


def old_text(it: dict) -> list[str]:
    o = it["old_answer"]
    if o is None:
        return []
    if it["format"] == "mcq":
        return [it["choices"]["ABCD".index(o)]]
    return o if isinstance(o, list) else [o]


def check_items(items: list[dict]) -> list[str]:
    errs: list[str] = []
    E = errs.append
    ids = Counter(it.get("id") for it in items)
    for k, v in ids.items():
        if v > 1:
            E(f"{k}: duplicate id")
    for it in items:
        iid = it.get("id")
        for k in REQ:
            if k not in it:
                E(f"{iid}: missing field {k}")
        for k in REQ_META:
            if k not in it.get("meta", {}):
                E(f"{iid}: missing meta.{k}")
        if not _is_nfc(it):
            E(f"{iid}: text not NFC")
        for p in lint_item(it):
            E(f"lint {p}")
        if it["format"] == "mcq":
            if it["answer"] not in "ABCD"[: len(it["choices"])]:
                E(f"{iid}: answer letter out of range")
            if it["old_answer"] is not None and it["old_answer"] == it["answer"]:
                E(f"{iid}: old_answer letter equals answer")
            if len(set(it["choices"])) != len(it["choices"]):
                E(f"{iid}: duplicate choices")
        else:
            if it["choices"] is not None:
                E(f"{iid}: short item has choices")
            for o in old_text(it):
                if normalize_text(o) == normalize_text(it["answer"]):
                    E(f"{iid}: old_answer equals answer")
    return errs


def _mask_names(q: str, m: dict) -> str:
    out = q
    names = [m.get(k) for k in ("old_ward_name", "old_district_name", "old_province_name", "new_ward_name",
                                "new_province_name", "entity_name")]
    for n in sorted({x for x in names if x}, key=len, reverse=True):
        for v in (n, lower_prefix(n), short_of(n)):
            out = out.replace(v, " ")
            out = re.sub(re.escape(v), " ", out, flags=re.I)
    return out


def check_cues(items: list[dict]) -> list[str]:
    errs: list[str] = []
    groups: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        if it["qtype"] in CUE_QTYPES:
            groups[it["meta"]["cue_group"]].append(it)
    for g, lst in groups.items():
        cues = sorted(it["meta"]["cue"] for it in lst)
        if cues != ["date", "none", "reform"]:
            errs.append(f"{g}: cue variants {cues}")
            continue
        by = {it["meta"]["cue"]: it for it in lst}
        base = by["none"]
        for c, pre in (("date", "Tính đến tháng 10/2026, "), ("reform", "Sau đợt sắp xếp đơn vị hành chính năm 2025, ")):
            it = by[c]
            if it["id"] != f"{g}__{c}":
                errs.append(f"{it['id']}: id does not follow <cue_group>__<cue>")
            if not it["question"].startswith(pre) or it["question"][len(pre):] != base["question"][:1].lower() + base["question"][1:]:
                errs.append(f"{it['id']}: wording differs from cue=none beyond the prefix")
            for f in ("choices", "answer", "old_answer", "answer_aliases"):
                if it[f] != base[f]:
                    errs.append(f"{it['id']}: {f} differs across cue variants")
        masked = _mask_names(base["question"], base["meta"])
        mk = CUE_MARKERS.search(masked.lower())
        if mk:
            errs.append(f"{base['id']}: cue=none question contains marker {mk.group(0)!r}: {base['question']}")
    return errs


def check_leakage(items: list[dict]) -> list[str]:
    """A changed gold component (with its unit prefix) must not occur in the question."""
    errs = []
    for it in items:
        m = it["meta"]
        # normalize_text drops punctuation; keep segment boundaries as " | " so that a gold that
        # is only the beginning of a longer old name ("Xã Định Thành" in "xã Định Thành A") is
        # not counted as a leak
        q = " | ".join(normalize_text(x) for x in re.split(r"[,.;:?()]", it["question"]))
        comps: list[str] = []
        if it["qtype"] in ("T1_membership", "T6_reverse", "T1_newname"):
            if m.get("surface_answer_changed") or it["old_answer"] is not None:
                comps.append(gold_text(it))
        elif it["qtype"] == "T5_ward_successor":
            if it["old_answer"] is not None:
                comps.append(gold_text(it))
        elif it["qtype"] == "T4_address":
            if m.get("name_changed") and key(short_of(m["old_ward_name"])) != key(short_of(m["gold_ward"])):
                comps.append(m["gold_ward"])
            if m.get("province_name_changed"):
                comps.append(m["gold_province"])
        for cmp in comps:
            pat = r"(?<!\w)" + re.escape(normalize_text(cmp)) + r"(?= \||$| thuộc)"
            if re.search(pat, q):
                errs.append(f"{it['id']}: changed gold {cmp!r} leaks into the question")
            if m.get("has_diacritics") is False and re.search(
                    r"(?<!\w)" + re.escape(strip_diacritics(normalize_text(cmp))) + r"(?= \||$| thuoc)", strip_diacritics(q)):
                errs.append(f"{it['id']}: changed gold {cmp!r} leaks into the question (no diacritics)")
    return errs


def check_gold(items: list[dict], t) -> list[str]:
    """Re-derive every ward-level gold from ward_mapping."""
    errs = []
    for it in items:
        m = it["meta"]
        oc = m.get("old_ward_code")
        if it["qtype"] in ("T1_membership", "T4_address", "T5_ward_successor") or (oc and it["qtype"] == "T3_existence"):
            rows = t.rows_by_old.get(oc, [])
            if not rows or any(r["confidence"] != "high" for r in rows):
                errs.append(f"{it['id']}: old ward {oc} has no high-confidence mapping")
                continue
            prov = {r["new_province_name"] for r in rows}
            if it["qtype"] == "T1_membership" and gold_text(it) not in prov:
                errs.append(f"{it['id']}: gold {gold_text(it)!r} not the mapped province {prov}")
            if it["qtype"] in ("T4_address", "T5_ward_successor"):
                if len(rows) != 1:
                    errs.append(f"{it['id']}: divided ward used for a ward-level gold")
                    continue
                r = rows[0]
                want = r["new_ward_name"] if it["qtype"] == "T5_ward_successor" else f"{r['new_ward_name']}, {r['new_province_name']}"
                if gold_text(it) != want:
                    errs.append(f"{it['id']}: gold {gold_text(it)!r} != mapping {want!r}")
        if it["qtype"] == "T1_newname":
            w = t.wnew[m["new_ward_code"]]
            if gold_text(it) != t.pnew[w["province_code"]]["name"] or t.new_ward_key_count[key(w["short_name"])] != 1:
                errs.append(f"{it['id']}: T1_newname gold/uniqueness problem")
        if it["qtype"] == "T6_reverse":
            if gold_text(it) != t.pnew[t.new_of_old_prov[m["old_province_code"]]]["name"]:
                errs.append(f"{it['id']}: T6 gold wrong")
    return errs


def check_balance(items: list[dict]) -> list[str]:
    errs = []
    t3 = Counter(it["meta"]["t3_exists"] for it in items if it["qtype"] == "T3_existence")
    if t3 and abs(t3[True] - t3[False]) > 0.1 * sum(t3.values()):
        errs.append(f"T3 yes/no imbalance: {dict(t3)}")
    by: dict[str, Counter] = defaultdict(Counter)
    for it in items:
        if it["format"] == "mcq":
            by[it["qtype"]][it["answer"]] += 1
    for q, c in by.items():
        n = sum(c.values())
        if n >= 100 and max(c.values()) > 0.4 * n:
            errs.append(f"{q}: MCQ answer letters unbalanced {dict(c)}")
    return errs


def check_contexts(items: list[dict], ctx: list[dict], passages: dict[str, dict]) -> list[str]:
    errs = []
    by: dict[tuple[str, str], dict] = {}
    for r in ctx:
        k = (r["item_id"], r["condition"])
        if k in by:
            errs.append(f"{k}: duplicate context row")
        by[k] = r
    for it in items:
        iid = it["id"]
        for cond in ("none", "new", "mixed"):
            if (iid, cond) not in by:
                errs.append(f"{iid}: no {cond} context")
        if errs and errs[-1].startswith(iid):
            continue
        if by[(iid, "none")]["passages"]:
            errs.append(f"{iid}: none context has passages")
        new, mixed = by[(iid, "new")], by[(iid, "mixed")]
        for pid in new["passages"] + mixed["passages"]:
            if pid not in passages:
                errs.append(f"{iid}: unknown passage {pid}")
        if errs and errs[-1].startswith(iid):
            continue
        if len(new["passages"]) != 1 or passages[new["passages"][0]]["era"] != "new":
            errs.append(f"{iid}: new context must be one new-era passage")
            continue
        npid = new["passages"][0]
        ntext = passages[npid]["text"]
        must = list(new.get("must_contain") or [])
        # the gold names themselves must be among the verified strings
        m = it["meta"]
        gold_names: list[str] = []
        if it["qtype"] in ("T1_membership", "T6_reverse", "T1_newname"):
            gold_names = [short_of(gold_text(it))]
        elif it["qtype"] == "T5_ward_successor":
            gold_names = [short_of(gold_text(it))]
        elif it["qtype"] == "T4_address":
            gold_names = [short_of(m["gold_ward"]), short_of(m["gold_province"])]
        mk = {key(x) for x in must} | {key(short_of(x)) for x in must}
        for gname in gold_names:
            if key(gname) not in mk:
                errs.append(f"{iid}: gold {gname!r} not in must_contain")
        for nm in must:
            if not has_name(nm, ntext):
                errs.append(f"{iid}: new passage {npid} lacks {nm!r}")
        mp = mixed["passages"]
        eras = [passages[p]["era"] for p in mp]
        if len(mp) != 2 or npid not in mp or sorted(eras) != ["new", "old"]:
            errs.append(f"{iid}: mixed must be one old + the same new passage ({mp})")
            continue
        opid = mp[eras.index("old")]
        for nm in mixed.get("must_contain_old") or []:
            if not has_name(nm, passages[opid]["text"]):
                errs.append(f"{iid}: old passage {opid} lacks {nm!r}")
        if it["old_answer"] is not None and it["qtype"] in ("T1_membership", "T6_reverse", "T1_newname", "T4_address"):
            want = m.get("old_province_name") or (m.get("old_answer_province") and None)
            if it["qtype"] == "T1_newname":
                want = m.get("old_province_name")
            if want and not has_name(short_of(want), passages[opid]["text"]):
                errs.append(f"{iid}: old passage lacks the old answer {want!r}")
        if it["old_answer"] is not None and it["qtype"] in ("T5_ward_successor", "T4_address"):
            if not has_name(wn(m["old_ward_name"]), passages[opid]["text"]):
                errs.append(f"{iid}: old passage lacks the old ward {m['old_ward_name']!r}")
        if not passages[opid]["revision_timestamp"] < passages[npid]["revision_timestamp"]:
            errs.append(f"{iid}: old passage is not older than the new one (+recency assumes it)")
        total = sum(len(passages[p]["text"]) for p in mp)
        if total > MAX_CTX:
            errs.append(f"{iid}: mixed context {total} chars > {MAX_CTX}")
        if m.get("context_source") not in ("wiki", "template"):
            errs.append(f"{iid}: meta.context_source missing")
    return errs


def check_passages(passages: dict[str, dict]) -> list[str]:
    errs = []
    wiki = {p["passage_id"]: p for p in load_jsonl(WIKI / "passages.jsonl")}
    for pid, p in passages.items():
        if pid in wiki:
            errs.append(f"{pid}: generated passage id collides with a wiki passage")
        for k in ("passage_id", "title", "revision_timestamp", "text", "era", "source"):
            if not p.get(k):
                errs.append(f"{pid}: missing {k}")
        if p["source"] == "template" and not pid.startswith("tpl_"):
            errs.append(f"{pid}: template id must start with tpl_")
        if p["source"] == "wiki_excerpt":
            src = wiki.get(p.get("derived_from"))
            if not pid.startswith("wikix_") or src is None:
                errs.append(f"{pid}: excerpt without a wiki source")
            elif src["revision_timestamp"] != p["revision_timestamp"] or src["era"] != p["era"]:
                errs.append(f"{pid}: excerpt metadata differs from its source")
        if not unicodedata.is_normalized("NFC", p["text"]):
            errs.append(f"{pid}: text not NFC")
    return errs


def check_twins(items: list[dict]) -> list[str]:
    errs = []
    by = {it["id"]: it for it in items}
    nd = [it for it in items if it["meta"].get("has_diacritics") is False]
    for it in nd:
        src = by.get(it["meta"].get("twin_id"))
        if src is None:
            errs.append(f"{it['id']}: twin source missing")
            continue
        if (src["answer"], src["old_answer"]) != (it["answer"], it["old_answer"]) or src["meta"].get("twin_id") != src["id"]:
            errs.append(f"{it['id']}: twin differs in gold or link")
        addr = it["question"].split("Địa chỉ cũ: ", 1)[1].split(". Địa chỉ này", 1)[0]
        if strip_diacritics(addr) != addr:
            errs.append(f"{it['id']}: twin address still has diacritics")
    return errs


def validate_dir(d: Path) -> list[str]:
    items = load_jsonl(d / "items.jsonl")
    ctx = load_jsonl(d / "contexts.jsonl")
    passages = {p["passage_id"]: p for p in load_jsonl(d / "template_passages.jsonl")}
    t = load_tables()
    errs = []
    for f in (check_items, check_cues, check_leakage, check_balance, check_twins):
        errs += f(items)
    errs += check_gold(items, t)
    errs += check_passages(passages)
    errs += check_contexts(items, ctx, passages)
    return errs


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    d = Path(argv[0]) if argv else BENCH
    errs = validate_dir(d)
    for e in errs[:200]:
        print(e)
    print(f"{len(errs)} problem(s)", file=sys.stderr)
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
