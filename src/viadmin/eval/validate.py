"""Lint benchmark items against what the scorer can reliably grade.

Run: ``uv run python -m viadmin.eval.validate data/benchmark/items.jsonl``
(also available as ``runner --validate``). Returns a list of human-readable problems;
the generator should drive this to zero (or justify each remaining entry).
"""

from __future__ import annotations

import json
import sys
from collections import Counter

from viadmin.eval.normalize import normalize_name, strip_diacritics
from viadmin.eval.scorer import LETTERS, _make_targets, _match, _old_letter, expand_key

# yes/no (T3) and unordered-list (T2) golds have no short-answer rule in the scorer
SHORT_UNSUPPORTED = {"T2_composition", "T3_existence"}
QTYPES = {"T0_headline", "T1_membership", "T2_composition", "T3_existence", "T4_address", "T6_reverse",
          # SPEC "Knowledge depth levels" addendum (deep items)
          "T1_newname", "T5_ward_successor"}


def lint_item(it: dict) -> list[str]:
    errs: list[str] = []
    iid = it.get("id", "?")
    E = lambda m: errs.append(f"{iid}: {m}")  # noqa: E731
    for k in ("id", "qtype", "question", "format", "answer"):
        if it.get(k) in (None, ""):
            E(f"missing {k}")
    if it.get("qtype") not in QTYPES:
        E(f"unknown qtype {it.get('qtype')!r}")
    if it.get("format") == "mcq":
        ch = it.get("choices") or []
        if len(ch) != 4:
            E(f"mcq has {len(ch)} choices (expected 4)")
        valid = LETTERS[: len(ch)]
        ans = str(it.get("answer", "")).strip()
        if len(ans) != 1 or ans not in valid:
            E(f"mcq answer {ans!r} not a letter in {valid}")
        norm = [normalize_name(c) for c in ch]
        dup = [k for k, v in Counter(norm).items() if v > 1]
        if dup:
            E(f"choices collide after normalisation: {dup}")
        if (it.get("meta") or {}).get("has_diacritics") is False:
            dup = [k for k, v in Counter(strip_diacritics(x) for x in norm).items() if v > 1]
            if dup:
                E(f"has_diacritics=false but choices collide without diacritics: {dup}")
        old = it.get("old_answer")
        if old is not None:
            ol = _old_letter(it)
            if ol is None:
                E(f"old_answer {old!r} does not map to any choice")
        # choices that the alias table treats as the same entity (e.g. "TP.HCM" and
        # "Thành phố Hồ Chí Minh") make the item unanswerable
        exp = [expand_key(k) for k in norm]
        for i in range(len(exp)):
            for j in range(i + 1, len(exp)):
                if norm[i] != norm[j] and (norm[i] in exp[j] or norm[j] in exp[i]):
                    E(f"choices {ch[i]!r} and {ch[j]!r} are aliases of each other")
    elif it.get("format") == "short":
        if it.get("choices"):
            E("short item has choices")
        if it.get("qtype") in SHORT_UNSUPPORTED:
            E(f"{it.get('qtype')} must be mcq: no short-answer scoring rule for yes/no or "
              "unordered-list golds (see SPEC Evaluation)")
        gold = _make_targets([it["answer"], *(it.get("answer_aliases") or [])])
        olds = [it.get("old_answer")] if isinstance(it.get("old_answer"), str) else (it.get("old_answer") or [])
        for o in olds:
            # old_answer textually different from answer but indistinguishable for the
            # scorer -> "outdated" can never be detected for this item
            if normalize_name(o) != normalize_name(it["answer"]) and _match(o, gold):
                E(f"old_answer {o!r} differs from answer {it['answer']!r} but the scorer accepts it as correct")
            # no-diacritic items are labelled with diacritic-insensitive matching: an old answer
            # that equals the gold once diacritics are removed (Tân Thành / Tân Thạnh) would be
            # labelled correct
            elif ((it.get("meta") or {}).get("has_diacritics") is False
                  and normalize_name(o) != normalize_name(it["answer"]) and _match(o, gold, nodiac=True)):
                E(f"has_diacritics=false but old_answer {o!r} and answer {it['answer']!r} are identical "
                  "without diacritics (outdated undetectable; choose another item)")
    else:
        E(f"unknown format {it.get('format')!r}")
    return errs


def lint_file(path: str) -> list[str]:
    errs: list[str] = []
    seen: set[str] = set()
    with open(path, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            if not line.strip():
                continue
            it = json.loads(line)
            if it.get("id") in seen:
                errs.append(f"{it.get('id')}: duplicate id (line {ln})")
            seen.add(it.get("id"))
            errs.extend(lint_item(it))
    return errs


if __name__ == "__main__":
    problems = lint_file(sys.argv[1] if len(sys.argv) > 1 else "data/benchmark/items.jsonl")
    for p in problems:
        print(p)
    print(f"{len(problems)} problem(s)", file=sys.stderr)
    sys.exit(1 if problems else 0)
