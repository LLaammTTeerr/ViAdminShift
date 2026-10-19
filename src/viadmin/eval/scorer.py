"""Answer parsing + labelling.

Every prediction gets one of four labels (SPEC "Evaluation"):

* ``correct``     - matches the gold answer (``answer`` / ``answer_aliases`` / alias table)
* ``outdated``    - matches ``old_answer`` (or a legacy name of the gold, e.g. Thừa Thiên Huế
                    for Huế) and NOT the gold. ``correct`` is always checked first, so items
                    whose old_answer equals the answer can never be labelled outdated.
* ``other_wrong`` - a parseable answer that is neither
* ``invalid``     - nothing parseable (no letter for MCQ; empty/abstention for short)

``match_detail`` records *how* the label was reached (exact, alias, first_segment,
contained, address_suffix, legacy_name, soft_alias, ambiguous, ...) so lenient or
stricter re-scorings can be computed later without re-running models.

Every result also carries ``label_nodiac``: the same pipeline run with diacritic-
insensitive matching against gold, old AND legacy names (so "Binh Duong" for an old
answer "Bình Dương" is ``outdated``, not ``other_wrong``). For items whose question is
written WITHOUT diacritics (``meta.has_diacritics == False``) the main ``label`` IS the
diacritic-insensitive label (the ablation varies the input, it does not ask the model to
restore diacritics); ``label_strict`` always keeps the diacritic-sensitive label.

Aliases are expanded on the gold side only; the prediction is only normalised.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from viadmin.eval import aliases as _aliases
from viadmin.eval.normalize import (
    admin_level,
    expand_abbreviations,
    levels_compatible,
    nfc,
    nodiac_keys,
    normalize_name,
    normalize_text,
    preceding_level,
    strip_diacritics,
)

LABELS = ("correct", "outdated", "other_wrong", "invalid")
LETTERS = "ABCDEFGH"

# Set to False to disable the "gold name contained in a longer sentence" fallback for
# short answers (it is reported via match_detail="contained" either way).
ALLOW_CONTAINMENT = True


@dataclass
class ScoreResult:
    parsed: str | None
    label: str
    match_detail: str | None = None
    correct_nodiac: bool | None = None  # label_nodiac == "correct"
    label_nodiac: str | None = None  # diacritic-insensitive label (MCQ: == label)
    label_strict: str | None = None  # diacritic-sensitive label (short answers)
    # T4 addresses (items with meta.gold_ward + meta.gold_province): per-component labels
    # {"ward": label, "province": label}, see score_address_components
    components: dict[str, str] | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- cleaning

_THINK_RE = re.compile(r"<think>.*?</think>", re.S | re.I)
_MD_RE = re.compile(r"[*`_]{1,3}")


def clean_output(raw: str | None) -> str:
    """Strip <think> blocks (closed or dangling), markdown emphasis, outer whitespace."""
    if not raw:
        return ""
    s = nfc(raw)
    s = _THINK_RE.sub(" ", s)
    if "<think>" in s.lower():  # unterminated reasoning: nothing usable after it
        s = s[: s.lower().index("<think>")]
    s = s.replace("</think>", " ")
    s = _MD_RE.sub("", s)
    return s.strip()


class _Rx:
    """A regex with a diacritic-free twin, used when the prediction itself has no
    diacritics at all ("Phuong Sai Gon thuoc TP HCM")."""

    def __init__(self, pattern: str, flags: int = re.I):
        self.d = re.compile(pattern, flags)
        self.n = re.compile(strip_diacritics(pattern), flags)

    def get(self, plain: bool) -> re.Pattern:
        return self.n if plain else self.d


def _is_plain(s: str) -> bool:
    return bool(s) and s == strip_diacritics(s)


# --------------------------------------------------------------------------- MCQ

_KW = (
    r"(?:đáp\s*án|câu\s*trả\s*lời|trả\s*lời|lựa\s*chọn|phương\s*án|chọn|answer|option)"
    r"(?:\s+(?:đúng|chính\s*xác|cuối\s*cùng|is|correct))*"
    r"(?:\s+(?:nhất))?"
    r"(?:\s+(?:là|is))?"
)


_GUESS = r"(?<!\w)(?:đoán|thiên\s+về|nghiêng\s+về)(?:\s+(?:là|rằng))?"
_MCQ_REFUSAL_RE = re.compile(
    r"không\s+thể\s+chọn|không\s+có\s+(?:đáp\s+án|lựa\s+chọn|phương\s+án)\s+(?:nào\s+)?(?:đúng|phù\s+hợp|chính\s+xác)",
    re.I,
)


def _letter_regexes(valid: str) -> tuple[re.Pattern, re.Pattern, re.Pattern]:
    cls = f"[{valid}]"
    bare = re.compile(rf"^[\s(\[]*({cls}|{cls.lower()})[\s.)\]:]*$")
    kw = re.compile(rf"{_KW}\s*[:：\-]?\s*[(\[]?({cls})(?![\wÀ-ỹ])", re.I | re.UNICODE)
    lead = re.compile(rf"^(?:\(({cls})\)|\[({cls})\]|({cls})\s*[.):])(?:\s|$)")
    return bare, kw, lead


_LOWER_OK_RE = re.compile(r"^[)\]]?\s*(?:[.:!]\s*)?$|^[)\]]?\s*[.):]\s")


def _kw_letters(kw: re.Pattern, text: str) -> list[tuple[str, int]]:
    """(letter, position) for every keyword hit. The keyword part is case-insensitive.
    An upper-case letter is always accepted; a lower-case one only when it ends the
    answer or is followed by a hard delimiter ("đáp án là b", "đáp án: b."), so
    "chọn a" inside running text is not read as a letter."""
    out = []
    for m in kw.finditer(text):
        letter = text[m.start(1) : m.end(1)]
        if letter.isupper() or _LOWER_OK_RE.match(text[m.end(1) :]):
            out.append((letter.upper(), m.start(1)))
    return out


def _letterish(choices: list[str]) -> list[tuple[int, str]]:
    """Choices whose (prefix-stripped) text itself starts with a lone letter: "A Lưới 1",
    "B'Lao" -> (index, normalised text)."""
    out = []
    for i, c in enumerate(choices):
        k = normalize_name(c)
        if re.match(r"^[a-h] ", k):
            out.append((i, k))
    return out


def _starts_choice_text(text: str, pos: int, letterish: list[tuple[int, str]]) -> bool:
    """True if the letter at ``pos`` is the first character of a letterish choice text
    ("Đáp án: A Lưới" -> the "A" belongs to the name, not a letter answer)."""
    rest = normalize_text(text[pos : pos + 60])
    return any(rest == k or rest.startswith(k + " ") for _, k in letterish)


def _choice_keys(choices: list[str]) -> list[frozenset[str]]:
    """Normalised choice texts expanded with EQUIVALENT aliases (TP.HCM, HCM, ...)."""
    return [expand_key(normalize_name(c)) for c in choices]


def extract_letter(raw: str | None, choices: list[str]) -> tuple[str | None, str | None]:
    """Return (letter, how) or (None, reason).

    Order: bare letter -> keyword ("Đáp án: B") -> leading letter with a hard delimiter
    ("B.", "B)", "(B)", "B:") -> a choice text that starts with a lone letter ("A Lưới")
    -> trailing "... là B" -> unique choice-text match (aliases expanded; relation clause
    "X sáp nhập vào Y" resolved to Y). A keyword/leading letter that is in fact the first
    letter of such a choice text ("Đáp án: A Lưới") is not taken as a letter. A bare
    leading letter followed only by a space is NOT accepted ("A Lưới" is a place name).
    Runs on the diacritised text (never strip diacritics first: "Đáp án" -> "Dap an").
    """
    text = clean_output(raw)
    if not text:
        return None, "empty"
    valid = LETTERS[: len(choices)] if choices else "ABCD"
    bare, kw, lead = _letter_regexes(valid)

    m = bare.match(text)
    if m:
        return m.group(1).upper(), "bare"
    # bare letter on the first line followed by an explanation ("C\n\nGiải thích: ...")
    m = bare.match(text.splitlines()[0])
    if m:
        return m.group(1).upper(), "bare_first_line"
    # reasoning first, then the letter alone on the last line ("Theo Nghị quyết ...\n\n**A**")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) > 1:
        m = bare.match(lines[-1])
        if m:
            return m.group(1).upper(), "bare_last_line"

    letterish = _letterish(choices) if choices else []
    first_line = text.splitlines()[0].strip()

    letters = [L for L, pos in _kw_letters(kw, text) if not _starts_choice_text(text, pos, letterish)]
    if letters:
        if len(set(letters)) > 1:
            return None, "multiple_letters"
        return letters[0], "keyword"

    # a guessed letter is a committed letter ("Nếu buộc phải chọn, tôi đoán là B, nhưng ...")
    guesses = {m.group(1) for m in re.finditer(rf"{_GUESS}\s*[:：]?\s*[(\[]?([{valid}])(?![\wÀ-ỹ])", text, re.I)
               if m.group(1).isupper()}
    if len(guesses) == 1:
        return guesses.pop(), "guess"
    # an explicit refusal to choose: the choice names it repeats are not an answer
    if _MCQ_REFUSAL_RE.search(text):
        return None, "abstain"

    m = lead.match(first_line)
    if m:
        g = next(i for i in (1, 2, 3) if m.group(i))
        if not _starts_choice_text(first_line, m.start(g), letterish):
            return m.group(g), "leading"

    # Choices whose text itself starts with a lone letter ("Xã A Lưới 1"), mentioned
    # without any explicit letter.
    if letterish:
        nt = normalize_text(text)
        hits = [i for i, k in letterish if _contains(nt, k)]
        if len(hits) == 1:
            return valid[hits[0]], "choice_text"

    m = re.search(rf"(?:^|\s)(?:là|chọn|is)\s+[(\[]?([{valid}])[)\]]?\s*[.!]?\s*$", text, re.I)
    if m and text[m.start(1)].isupper():
        return m.group(1), "trailing"

    # Text-only answers: match against choice texts.
    if choices:
        ck = _choice_keys(choices)
        norm_choices = [normalize_name(c) for c in choices]
        cands = {normalize_name(first_line), normalize_name(_first_segment(first_line))}
        cands.discard("")
        hits = [i for i, keys in enumerate(ck) if keys & cands]
        if len(hits) == 1:
            return valid[hits[0]], "choice_text"
        nt = normalize_text(text)

        def contained(hay: str) -> list[int]:
            h = [i for i, keys in enumerate(ck) if any(_contains(hay, k) for k in keys)]
            # drop hits whose text is contained in another hit ("An Phú" vs "Tân An Phú")
            return [i for i in h if not any(j != i and _contains(norm_choices[j], norm_choices[i]) for j in h)]

        hits = contained(nt)
        if len(hits) == 1:
            return valid[hits[0]], "choice_text_contained"
        if len(hits) > 1:
            # "Tỉnh Bình Dương đã sáp nhập vào Thành phố Hồ Chí Minh": the relation
            # clause names the answer.
            tails = _relation_tails(_strip_past(first_line), _REL)
            th = contained(normalize_text(" , ".join(tails))) if tails else []
            if len(th) == 1:
                return valid[th[0]], "choice_text_relation"
            return None, "multiple_choice_texts"
    return None, "no_letter"


# --------------------------------------------------------------------------- short

_ANSWER_LEAD_RE = re.compile(
    r"^\s*(?:(?:đáp\s*án|câu\s*trả\s*lời|trả\s*lời|answer)(?:\s+(?:đúng|là))*"
    r"|địa\s+chỉ(?:\s+(?:mới|hiện\s+nay|hiện\s+tại|sau\s+sáp\s+nhập|đầy\s+đủ))*(?:\s+là)?)"
    r"\s*[:：\-]?\s*",
    re.I,
)
# A spaced dash separates segments only before a unit prefix ("X - Thành phố Y"); real
# names keep theirs ("Bà Rịa - Vũng Tàu", "Văn Miếu - Quốc Tử Giám", "Lâm Viên - Đà Lạt").
_SEG_SPLIT_RE = re.compile(
    r"[,;(\[]|\s/\s|\s[-–—]{1,2}\s+(?=(?:phường|xã|thị\s+trấn|đặc\s+khu|quận|huyện|thị\s+xã|tỉnh|"
    r"thành\s+phố|tp|phuong|xa|thi\s+tran|dac\s+khu|quan|huyen|thi\s+xa|tinh|thanh\s+pho)(?!\w))",
    re.I,
)
_ABSTAIN_CORE = (
    r"(?:không|chưa)\s+(?:biết|rõ|chắc|nắm\s+(?:rõ|chắc|được)|có\s+(?:đủ\s+|nhiều\s+)?thông\s+tin"
    r"|thể\s+(?:xác\s+định|xác\s+nhận|khẳng\s+định|trả\s+lời))"
)
# Hedges: "Không chắc, nhưng có lẽ là X", "Tôi không có đủ thông tin, nhưng có lẽ là X"
# -> score X.
_HEDGE_WORD = r"(?:có\s+lẽ|có\s+thể|khả\s+năng(?:\s+cao)?|tôi\s+nghĩ|theo\s+tôi(?!\s+(?:được\s+)?biết)|hình\s+như|chắc\s+là)"
_HEDGE_RE = _Rx(
    rf"^(?:(?:tôi\s+)?(?:không\s+dám\s+chắc|{_ABSTAIN_CORE})(?!\w)[^,.;:\n]{{0,40}}?\s*[,.;:\-–]?\s*"
    rf"(?:(?:nhưng|tuy\s+nhiên)\s*,?\s*(?:{_HEDGE_WORD}\s*(?:là\s+)?)?|{_HEDGE_WORD}\s*(?:là\s+)?)"
    rf"|{_HEDGE_WORD}\s*(?:là\s+)?)[,:]?\s*(?=\S)"
)
_ABSTAIN_RE = _Rx(
    rf"^(?:tôi\s+)?(?:{_ABSTAIN_CORE}|xin\s+lỗi|i\s+(?:don'?t|do\s+not)\s+know)(?!\w)"
    r"|^(?:unknown|n/a|na|không\s+có)\s*[.!]?$"
)
# An abstention at the start of any sentence, clause or parenthetical of the output ("Xã X
# không còn tồn tại; tôi không chắc chắn về đơn vị mới"), also after a sentence adverbial
# ("Tuy nhiên, tôi không có thông tin chắc chắn") or as a consequence clause (", nên không
# thể xác nhận"), unless that clause goes on to hedge an answer ("Tôi không chắc, nhưng có
# lẽ là X").
_ABSTAIN_LEAD = (
    r"(?:tuy\s+nhiên|song|nhưng|rất\s+tiếc|đáng\s+tiếc|thực\s+tế|thực\s+ra|thật\s+ra|hiện\s+tại|hiện\s+nay|"
    r"hiện|do\s+đó|vì\s+vậy|vì\s+thế|cho\s+nên|nên|nói\s+chung|tóm\s+lại|nhìn\s+chung|ngoài\s+ra|cụ\s+thể|"
    r"xin\s+lỗi|theo\s+tôi(?:\s+biết)?|về\s+cơ\s+bản|đến\s+nay|tính\s+đến\s+nay)"
)
_ABSTAIN_CLAUSE_RE = _Rx(
    rf"(?:(?:^|[.;!?:(\n]\s*)(?:{_ABSTAIN_LEAD}\s*,?\s+)?|(?:,\s*|\s)(?:nên|cho\s+nên|vì\s+vậy|do\s+đó)\s+)"
    rf"(?:tôi\s+|mình\s+)?{_ABSTAIN_CORE}(?!\w)"
    rf"(?![^.;!?\n]*(?:nhưng|tuy\s+nhiên|{_HEDGE_WORD})(?!\w))"
)
# A last line that announces the answer: "Trả lời tốt nhất theo trí nhớ: xã Suối Tọ",
# "Nếu buộc phải đưa ra đáp án, tôi cho rằng: xã Nậm Sỏ".
_FINAL_LEAD_RE = _Rx(
    r"^[^:\n]{0,80}?(?<!\w)(?:đáp\s+án|trả\s+lời|kết\s+luận|cho\s+rằng|nhớ|tóm\s+lại|vậy|là|chọn|theo)(?!\w)"
    r"[^:\n]{0,40}:\s*(?=\S)"
)
_SENT_END_RE = re.compile(r"(?<![Tt][Pp])(?<![Tt][Xx])[.;?!](?=\s|$)")


def _first_segment(s: str) -> str:
    return _SEG_SPLIT_RE.split(s, maxsplit=1)[0].strip()


def _contains(hay: str, needle: str) -> bool:
    return bool(needle) and re.search(rf"(?<!\S){re.escape(needle)}(?!\S)", hay) is not None


def _answer_line(raw: str | None) -> str:
    text = expand_abbreviations(clean_output(raw))
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""
    line = _ANSWER_LEAD_RE.sub("", lines[0]).strip()
    if not line and len(lines) > 1:
        line = lines[1]
    return line.strip().rstrip(".。!").strip().strip("\"'“”‘’").strip()


def _clean_short(raw: str | None) -> str:
    line = _answer_line(raw)
    for _ in range(2):  # "Không chắc, nhưng có lẽ là X"
        line = _HEDGE_RE.get(_is_plain(line)).sub("", line, count=1).strip()
    return line


# alias lookups ---------------------------------------------------------------

def _build_equiv() -> dict[str, frozenset[str]]:
    idx: dict[str, frozenset[str]] = {}
    for group in _aliases.EQUIVALENT:
        keys = frozenset(normalize_name(x) for x in group)
        for k in keys:
            idx[k] = idx.get(k, frozenset()) | keys
    return idx


def _build_map(table: dict[str, list[str]]) -> dict[str, frozenset[str]]:
    out: dict[str, frozenset[str]] = {}
    for gold, names in table.items():
        out[normalize_name(gold)] = frozenset(normalize_name(n) for n in names)
    return out


_EQUIV = _build_equiv()
_PROVINCE_KEYS = frozenset(normalize_name(x) for x in _aliases.PROVINCE_NAMES)
_LEGACY = _build_map(_aliases.LEGACY)
_SOFT = _build_map(_aliases.SOFT)


def expand_key(key: str) -> frozenset[str]:
    return _EQUIV.get(key, frozenset({key}))


def _expand_with(key: str, table: dict[str, frozenset[str]]) -> set[str]:
    out: set[str] = set()
    for k in expand_key(key):
        out |= table.get(k, frozenset())
    return out


def _as_list(x: Any) -> list[str]:
    if x is None:
        return []
    if isinstance(x, str):
        return [x] if x.strip() else []
    return [str(v) for v in x if v is not None and str(v).strip()]


_DROP_SEGS = ("việt nam", "vn", "vietnam", "viet nam")


def _segments(s: str) -> list[str]:
    segs = [x.strip() for x in re.split(r"[,;\n]", s) if normalize_name(x)]
    return [x for x in segs if normalize_name(x) not in _DROP_SEGS]


def _eff_level(raw_seg: str, key: str) -> str | None:
    """Explicit prefix level, or "PC" for an unprefixed (pre-reform) province name."""
    lv = admin_level(raw_seg)
    if lv is None and key in _PROVINCE_KEYS:
        return "PC"
    return lv


@dataclass
class _Target:
    """One acceptable answer: a list of segments, each a set of accepted keys.

    levels[i]: admin level of the gold segment ('W'/'D'/'P'/'C'/'PC'/None, see
        normalize.admin_level and _eff_level).
    strict_prefix[i]: the gold is a ward whose bare name is also a province name
        ("Phường Bình Dương"), so the prediction must carry a ward-level prefix.
    """

    segs: list[frozenset[str]]
    nodiac: list[frozenset[str]]
    levels: list[str | None]
    strict_prefix: list[bool]
    alias_used: bool = False


def _nod(segs: list[frozenset[str]]) -> list[frozenset[str]]:
    return [frozenset().union(*(nodiac_keys(k) for k in b)) for b in segs]


def _make_targets(surfaces: Iterable[str], table: dict[str, frozenset[str]] | None = None) -> list[_Target]:
    """Gold-side expansion. With ``table`` (LEGACY / SOFT), every segment that has an
    entry in that table is replaced by the table's names (one target per such seg)."""
    targets: list[_Target] = []
    primary: list[str | None] | None = None  # explicit levels of the first surface (the answer)
    for s in surfaces:
        raw_segs = _segments(s)
        if not raw_segs:
            continue
        keys = [normalize_name(x) for x in raw_segs]
        levels = [_eff_level(x, k) for x, k in zip(raw_segs, keys)]
        if primary is None:
            primary = [admin_level(x) for x in raw_segs]
        elif len(primary) == len(raw_segs):
            # an unprefixed alias ("Vũng Tàu" for "Phường Vũng Tàu") inherits the answer's
            # level, so it cannot bypass the level checks ("Thành phố Vũng Tàu" stays wrong)
            levels = [pl if admin_level(x) is None and pl else lv for x, lv, pl in zip(raw_segs, levels, primary)]
        strict = [lv == "W" and k in _PROVINCE_KEYS for lv, k in zip(levels, keys)]
        base = [expand_key(k) for k in keys]
        if table is None:
            targets.append(_Target(base, _nod(base), levels, strict))
            continue
        for i, k in enumerate(keys):
            alt = _expand_with(k, table)
            if not alt:
                continue
            segs = list(base)
            segs[i] = frozenset(alt)
            targets.append(_Target(segs, _nod(segs), levels, strict, alias_used=True))
    return targets


def _old_targets(surfaces: Iterable[str]) -> list[_Target]:
    """Old answers. For old addresses with >= 3 segments ("Phường Phú Cường, Thành phố
    Thủ Dầu Một, Tỉnh Bình Dương") an extra variant without the (abolished) middle
    district level is added ("Phường Phú Cường, Tỉnh Bình Dương"): a model that drops the
    district but keeps the old ward/province is still answering with the old structure."""
    out = _make_targets(surfaces)
    for t in list(out):
        if len(t.segs) >= 3:
            out.append(_Target([t.segs[0], t.segs[-1]], [t.nodiac[0], t.nodiac[-1]],
                               [t.levels[0], t.levels[-1]], [t.strict_prefix[0], t.strict_prefix[-1]]))
    return out


def _levels_ok(gold_level: str | None, strict: bool, pred_level: str | None) -> bool:
    if not levels_compatible(gold_level, pred_level):
        return False  # "Phường 1" vs "Quận 1"; "Phường Vũng Tàu" vs "Thành phố Vũng Tàu"
    if strict and pred_level != "W":
        return False  # bare "Bình Dương" for gold "Phường Bình Dương"
    return True


def _match(
    pred: str, targets: list[_Target], nodiac: bool = False, check_levels: bool = True, first: bool = True
) -> str | None:
    """Return match_detail if ``pred`` matches any target, else None."""
    if not pred or not targets:
        return None
    keyf = (lambda s: nodiac_keys(s)) if nodiac else (lambda s: {normalize_name(s)} - {""})

    first_raw = _first_segment(pred)
    full, first_k = keyf(pred), keyf(first_raw)
    lv_full, lv_first = admin_level(pred), admin_level(first_raw)
    pred_raw = _segments(pred)
    pred_segs = [keyf(x) for x in pred_raw]
    pred_lv = [admin_level(x) for x in pred_raw]

    def ok(t: _Target, i: int, lv: str | None) -> bool:
        return not check_levels or _levels_ok(t.levels[i], t.strict_prefix[i], lv)

    for t in targets:
        segs = t.nodiac if nodiac else t.segs
        if len(segs) == 1:
            if full & segs[0] and ok(t, 0, lv_full):
                return "exact" if not t.alias_used else "alias"
            if first and first_k & segs[0] and ok(t, 0, lv_first):
                return "first_segment"
        else:
            n, m = len(segs), len(pred_segs)
            if (m == n or first) and m >= n and all(pred_segs[m - n + i] & segs[i] and ok(t, i, pred_lv[m - n + i]) for i in range(n)):
                return "address" if m == n else "address_suffix"
    return None


def _contain_level_ok(level: str | None, strict: bool, pl: str | None) -> bool:
    """Level rule for a containment hit, given the level ``pl`` of the admin prefix
    immediately before the hit (None = no prefix there).

    * ward-level targets need an explicit ward prefix right before the name: this rejects
      "Quận/Huyện/Thị xã/Thành phố Hoàn Kiếm" for "Phường Hoàn Kiếm" and sub-spans such as
      "vũng tàu" inside "Tỉnh Bà Rịa - Vũng Tàu" for "Phường Vũng Tàu";
    * province/city-level targets reject hits right after a ward or district prefix
      ("Phường Bình Dương" is not the province Bình Dương)."""
    if level == "W" or strict:
        return pl == "W"
    if level in ("P", "C", "PC"):
        return pl not in ("W", "D")
    if level == "D":
        return pl in (None, "D", "C")
    return True


def _hits(hay: str, targets: list[_Target], nodiac: bool = False) -> list[tuple[int, int]]:
    """Spans of whole-token, level-compatible occurrences of single-segment targets in
    ``hay`` (a ``normalize_text``-ed string; diacritic-stripped when ``nodiac``)."""
    spans: list[tuple[int, int]] = []
    for t in targets:
        if len(t.segs) != 1:
            continue
        for k in (t.nodiac if nodiac else t.segs)[0]:
            if k.isdigit() or len(k) < 3:
                continue  # "1", "hn": too ambiguous for substring search
            for m in re.finditer(rf"(?<!\S){re.escape(k)}(?!\S)", hay):
                if _contain_level_ok(t.levels[0], t.strict_prefix[0], preceding_level(hay, m.start(), nodiac)):
                    spans.append((m.start(), m.end()))
    return spans


def _inside(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return b[0] <= a[0] and a[1] <= b[1] and a != b


def _contained_gold_old(
    text: str, gold: list[_Target], old: list[_Target], nodiac: bool = False
) -> tuple[bool, bool]:
    """(gold contained, old contained) in ``text``. A hit lying strictly inside a hit of
    the other set is discarded ("an phú" inside "tân an phú")."""
    hay = normalize_text(text)
    if nodiac:
        hay = strip_diacritics(hay)
    g = _hits(hay, gold, nodiac)
    o = _hits(hay, old, nodiac)
    g2 = [x for x in g if not any(_inside(x, y) for y in o)]
    o2 = [x for x in o if not any(_inside(x, y) for y in g) and x not in g]
    return bool(g2), bool(o2)


def _contained_text(pred_text: str, targets: list[_Target], nodiac: bool = False) -> bool:
    hay = normalize_text(pred_text)
    if nodiac:
        hay = strip_diacritics(hay)
    return bool(_hits(hay, targets, nodiac))


# Relation clauses in sentence answers: "X (cũ) nay thuộc Y", "X được sáp nhập vào Y",
# "X nay là Y". The answer is the clause AFTER the verb; the part before it is usually an
# echo of the question subject (often the OLD name) and must not be scored.
#
# "X sáp nhập với/cùng Y (và Z) thành/để thành lập W": the units after với/cùng are the
# other parts of the merger, the answer is W. Without a "thành" ("Tỉnh Tuyên Quang, sáp
# nhập cùng tỉnh Hà Giang") the partner is not an answer and no clause is read.
# "thành" must be lower-case: "sáp nhập với xã Thành Công thành xã Ea Kly".
_MERGE_WITH = (
    r"(?:sáp\s+nhập|hợp\s+nhất|nhập)\s+(?:với|cùng)(?:\s+với)?"
    r"[^.;:\n]*?\s(?:để\s+)?(?-i:thành)(?:\s+lập)?(?!\s+phố)"
)
_TRANSFORM = (
    r"được\s+sáp\s+nhập\s+vào|sáp\s+nhập\s+vào|được\s+hợp\s+nhất\s+vào|hợp\s+nhất\s+vào|"
    rf"nhập\s+vào|sắp\s+xếp\s+vào|{_MERGE_WITH}|sáp\s+nhập\s+thành|hợp\s+nhất\s+thành|"
    r"sắp\s+xếp\s+thành|chuyển\s+về|chuyển\s+thành|đổi\s+(?:tên\s+)?thành|trở\s+thành|là"
)
# "trực thuộc" only with a lower-case "trực" or in title case ("Thành Phố Trực Thuộc Trung
# Ương"): "Xã Nam Trực thuộc Tỉnh Ninh Bình" is the ward "Nam Trực" + "thuộc".
_MEMBER = r"(?-i:trực)\s+thuộc|(?-i:Trực\s+Thuộc)|thuộc\s+về|thuộc"
_REL = _Rx(rf"(?<!\w)(?:{_MEMBER}|{_TRANSFORM})(?!\w)")
_REL_TRANSFORM = _Rx(rf"(?<!\w)(?:{_TRANSFORM})(?!\w)")
_MEMBER_RE = _Rx(rf"\s*,?\s*(?<!\w)(?:{_MEMBER})(?!\w)\s*")
# A clause introduced by one of these describes the PAST and is ignored.
_PAST = (
    r"trước\s+đây|trước\s+kia|trước\s+năm|trước\s+ngày|trước\s+khi|trước\s+sáp\s+nhập|"
    r"trước\s+sắp\s+xếp|trước|từng|ban\s+đầu|cũ\s+là|vốn(?:\s+dĩ)?|nguyên\s+là|giảm\s+từ|"
    r"so\s+với|thay\s+vì|sáp\s+nhập\s+từ|hợp\s+nhất\s+từ"
)
_PAST_RE = _Rx(rf"(?<!\w)(?:{_PAST})(?!\w)")
# A negated verb ("không thuộc X", "không còn thuộc X", "chưa được sáp nhập vào X") does
# not name an answer.
_NEG_RE = _Rx(r"(?<!\w)(?:không|chưa|chẳng)(?:\s+(?:hề|còn|phải|được))?\s*$")
_PRESENT_RE = _Rx(
    r"(?<!\w)(?:nay|hiện\s+nay|hiện\s+tại|hiện|bây\s+giờ|sau\s+sáp\s+nhập|sau\s+sắp\s+xếp|"
    r"từ\s+ngày|kể\s+từ|sau\s+ngày|sau\s+khi)(?!\w)"
)
# Parentheticals describing the past / the origin are dropped entirely.
_PAREN_DROP_RE = _Rx(rf"(?<!\w)(?:{_PAST}|cũ|gồm|bao\s+gồm|nhập\s+từ)(?!\w)")
_PAREN_RE = re.compile(r"\(([^()]*)\)|\[([^\[\]]*)\]")
# A trailing clause starting with a past marker: ", trước đây là ...".
_TRAILING_PAST_RE = _Rx(rf"\s*[,;–—-]\s*(?:{_PAST})(?!\w).*$")
# "đơn vị hành chính cấp xã Võ Nhai" names the ward Võ Nhai; "đơn vị hành chính cấp xã"
# alone names nothing.
_TAIL_LEAD_RE = _Rx(
    r"^\s*(?:nay|hiện\s+nay|hiện|bây\s+giờ|hiện\s+tại|sau\s+sắp\s+xếp|địa\s+danh|đơn\s+vị(?:\s+hành\s+chính)?"
    r"(?:\s+cấp(?=\s+(?:phường|xã|thị\s+trấn|đặc\s+khu|quận|huyện|thị\s+xã|tỉnh|thành\s+phố)\s+\S))?)(?!\w)[\s,:]*"
)
_TAIL_CUT_RE = _Rx(
    r"(?<![Tt][Pp])(?<![Tt][Xx])\.|[;?!(\[]|,\s*(?:nay|hiện|trước|còn|và|nhưng)(?!\w)|\s(?:và|nhưng|còn|trước\s+đây|trước\s+kia)\s"
)
# A unit prefix followed by a proper name ("xã Văn Bàn", "Phường 12"), as opposed to a
# description ("xã mới thành lập", "thành phố trực thuộc trung ương", "xã loại I", in any
# capitalisation).
_NAMED_UNIT_RE = _Rx(
    r"^\s*(?:phường|xã|thị\s+trấn|đặc\s+khu|quận|huyện|thị\s+xã|tỉnh|thành\s+phố|tp)\.?\s*"
    r"(?!(?:trực\s+thuộc|thuộc|loại|cấp|hạng)(?!\w))(\S)"
)
# " - " is an address separator only when the right-hand side starts with a unit prefix
# ("Phường Sài Gòn - Thành phố Hồ Chí Minh"); names such as "Văn Miếu - Quốc Tử Giám",
# "Lâm Viên - Đà Lạt" or "Bà Rịa - Vũng Tàu" keep their hyphen.
_UNIT_HYPHEN_RE = _Rx(
    r"\s+[-–—]{1,2}\s+(?=(?:phường|xã|thị\s+trấn|đặc\s+khu|quận|huyện|thị\s+xã|tỉnh|thành\s+phố|tp)(?!\w))"
)


def _is_past_ctx(ctx: str, plain: bool) -> bool:
    ctx = ctx[-60:]
    past = list(_PAST_RE.get(plain).finditer(ctx))
    if not past:
        return False
    pres = list(_PRESENT_RE.get(plain).finditer(ctx))
    return not pres or past[-1].start() > pres[-1].start()


def _strip_past(line: str) -> str:
    """Drop past/origin parentheticals ("(cũ)", "(trước đây là X)", "(sáp nhập từ X)")
    and a trailing past clause (", trước đây thuộc X"); other parentheticals become a
    comma-separated segment ("X (Thành phố Hồ Chí Minh)" -> "X, Thành phố Hồ Chí Minh")."""
    plain = _is_plain(line)
    for _ in range(3):
        def rep(m: re.Match) -> str:
            inner = m.group(1) if m.group(1) is not None else m.group(2)
            if _PAREN_DROP_RE.get(plain).search(inner):
                return " "
            return ", " + inner + " "
        new = _PAREN_RE.sub(rep, line)
        if new == line:
            break
        line = new
    line = _TRAILING_PAST_RE.get(plain).sub("", line)
    return re.sub(r"\s+,", ",", re.sub(r"\s+", " ", line)).strip(" ,")


def _relation_tails(line: str, rel: _Rx = _REL) -> list[str]:
    """Answer candidates from relation clauses (present-tense ones only)."""
    plain = _is_plain(line)
    ms = list(rel.get(plain).finditer(line))
    tails = []
    for i, m in enumerate(ms):
        ctx = line[(ms[i - 1].end() if i else 0) : m.start()]
        if _is_past_ctx(ctx, plain) or _NEG_RE.get(plain).search(ctx[-24:]):
            continue
        end = ms[i + 1].start() if i + 1 < len(ms) else len(line)
        t = line[m.end() : end]
        t = _TAIL_CUT_RE.get(plain).split(t, maxsplit=1)[0]
        t = _TAIL_LEAD_RE.get(plain).sub("", t).strip(" ,:-–")
        if normalize_name(t):
            tails.append(t)
    return tails


def _names_unit(seg: str, levels: Iterable[str | None]) -> bool:
    """True if ``seg`` names a unit (prefix + capitalised or numbered name) at a level
    compatible with one of ``levels``: "xã Văn Bàn" for a ward gold, but not "tỉnh Lào
    Cai" (other level), "xã mới thành lập" or "đơn vị hành chính cấp xã" (no name)."""
    lv = admin_level(seg)
    if lv is None or not any(levels_compatible(g, lv) for g in levels):
        return False
    m = _NAMED_UNIT_RE.get(_is_plain(seg)).match(seg)
    return bool(m) and (m.group(1).isupper() or m.group(1).isdigit())


def _abstains(text: str) -> bool:
    return _ABSTAIN_CLAUSE_RE.get(_is_plain(text)).search(text) is not None


def _first_sentence(s: str) -> str:
    m = _SENT_END_RE.search(s)
    return s[: m.end()] if m else s


def _answer_form(line: str, levels: Iterable[str | None]) -> bool:
    """True if ``line`` is a bare name or address ("Xã Cao Lộc, tỉnh Lạng Sơn (chưa kiểm
    chứng)") rather than prose: no relation verb, abstention or question mark, at most four
    short segments, the first naming a unit at a level compatible with ``levels``."""
    if "..." in line or "…" in line:  # trailing off ("Xã Hạnh Nam... hãy xem:")
        return False
    s = _strip_past(_drop_prose_parens(line)).rstrip(".!")
    if not s or "?" in s or _REL.get(_is_plain(s)).search(s) or _abstains(s):
        return False
    segs = _segments(s)
    while len(segs) > 1 and _HOUSE_SEG_RE.get(_is_plain(segs[0])).match(segs[0]):  # "Số 9, thôn 3, xã Hạ Lang, ..."
        segs = segs[1:]
    return 0 < len(segs) <= 4 and all(len(x.split()) <= 6 for x in segs) and _names_unit(segs[0], levels)


# Leading address segments below the ward: house number, hamlet, street ("Số 9", "thôn 3", "ấp 4", "Tổ 5").
_HOUSE_SEG_RE = _Rx(r"^(?:số\s*\d|\d+[a-z]?(?:/\d+)*$|(?:thôn|ấp|tổ(?:\s+dân\s+phố)?|khu\s+phố|xóm|bản|khối|đội|"
                    r"đường|ngõ|ngách|hẻm|kiệt)\s+\S)")
# A last line that states the answer as such: a line that is bold as a whole ("**Xã Thái Bình, tỉnh Lạng Sơn**") or
# that opens with an answer or new-address label ("Câu trả lời: ...", "Địa chỉ hiện nay: ...").
_COMMIT_LINE_RE = re.compile(
    r"^\s*(?:\*\*[^*\n]+\*\*\s*[.!]?|(?:\*\*)?\s*(?:câu\s+trả\s+lời|đáp\s+án|trả\s+lời|địa\s+chỉ\s+(?:mới|hiện\s+nay|"
    r"hiện\s+tại|đúng|sau\s+sáp\s+nhập))(?:\s+(?:đúng|là))*\s*(?:\*\*)?\s*[:：].*)\s*$",
    re.I,
)


def _drop_prose_parens(line: str) -> str:
    """Drop parentheticals that hold a relation clause or an abstention ("Xã Vũ Thư, tỉnh
    Hưng Yên (Thái Bình sáp nhập vào Hưng Yên từ 01/7/2025)"); the others stay for
    :func:`_strip_past` ("(chưa kiểm chứng)", "(Thành phố Hồ Chí Minh)")."""
    plain = _is_plain(line)

    def rep(m: re.Match) -> str:
        inner = m.group(1) if m.group(1) is not None else m.group(2)
        return " " if _REL.get(plain).search(inner) or _abstains(inner) else m.group(0)

    return re.sub(r"\s+", " ", _PAREN_RE.sub(rep, line)).strip()


def _final_line(raw: str | None, levels: Iterable[str | None]) -> str | None:
    """The committed answer of a multi-line output: its last line when that is a bare name
    or address (after an announcing lead, "Trả lời tốt nhất theo trí nhớ: xã Suối Tọ") and
    the first line is not, i.e. reasoning first, then the answer alone on the last line, as
    for an MCQ letter. The last line of a list of such lines is not taken. A last line that
    states the answer as such (bold as a whole, or "Câu trả lời: ...", "Địa chỉ hiện nay:
    ...") is taken even after an echoed first line ("Địa chỉ cũ: ..." / "Địa chỉ hiện nay:
    ...")."""
    text = expand_abbreviations(clean_output(raw))
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return None
    raw_lines = [ln for ln in _THINK_RE.sub(" ", nfc(raw or "")).splitlines() if ln.strip()]
    stated = bool(raw_lines) and _COMMIT_LINE_RE.match(raw_lines[-1]) is not None
    if not stated and _answer_form(_first_sentence(_clean_short(raw)), levels):
        return None

    def strip(line: str) -> str:
        line = _ANSWER_LEAD_RE.sub("", _FINAL_LEAD_RE.get(_is_plain(line)).sub("", line))
        line = _first_sentence(line)
        if "..." in line or "…" in line:  # trailing off ("Xã Ea Kuăng... hãy xem lại")
            return ""
        line = _drop_prose_parens(line).strip().rstrip(".。!").strip().strip("\"'“”‘’").strip()
        for _ in range(2):
            line = _HEDGE_RE.get(_is_plain(line)).sub("", line, count=1).strip()
        return line

    last = strip(lines[-1])
    if not _answer_form(last, levels) or (not stated and _answer_form(strip(lines[-2]), levels)):
        return None
    return last


def _drop_same_as_gold(old: list[_Target], gold: list[_Target], nodiac: bool = False) -> list[_Target]:
    """Old targets identical (after normalisation/aliases) to a gold target can never
    signal outdatedness (e.g. unchanged province: answer == old_answer)."""
    out = []
    for t in old:
        ts = t.nodiac if nodiac else t.segs
        same = any(
            len(g.segs) == len(t.segs) and all(a & b for a, b in zip(g.nodiac if nodiac else g.segs, ts)) for g in gold
        )
        if not same:
            out.append(t)
    return out


# numbers ----------------------------------------------------------------------

_DATE_RE = re.compile(
    r"\b\d{1,2}\s*[/.\-]\s*\d{1,2}\s*[/.\-]\s*\d{2,4}\b"  # 1/7/2025, 01-07-2025
    r"|\b\d{1,2}\s*/\s*\d{4}\b"  # 7/2025
    r"|(?<!\w)(?:ngày|tháng|năm|ngay|thang|nam)\s+\d{1,4}(?!\w)"  # ngày 1, tháng 7, năm 2025
    r"|\b\d+\s*/\s*\d{4}\s*/\s*[\w\-]+"  # 202/2025/QH15
    r"|\b\d+\s*/\s*NQ[\w\-]*",
    re.I,
)
_THOUSANDS_RE = re.compile(r"(?<=\d)[.,](?=\d{3}(?!\d))")
_NUM_RE = re.compile(r"(?<![\w/])\d+(?![\w/])")
_FROM_TO_RE = re.compile(r"(?<!\w)từ\s+(\d+)(?=[^\d]{0,40}?(?:xuống|còn)\s+(?:còn\s+)?\d)", re.I)


_DIGIT_WORDS = {"một": 1, "mốt": 1, "hai": 2, "ba": 3, "bốn": 4, "tư": 4, "năm": 5, "lăm": 5, "sáu": 6, "bảy": 7,
                "tám": 8, "chín": 9}
_D = "(?:một|hai|ba|bốn|năm|sáu|bảy|tám|chín)"
_U = "(?:mốt|một|hai|ba|bốn|tư|năm|lăm|sáu|bảy|tám|chín)"
# A number in words before a counting noun ("Hai cấp", "ba mươi bốn tỉnh"); "năm" alone is also "year", hence the noun.
_NUM_WORDS_RE = re.compile(
    rf"(?<!\w)({_D}\s+mươi(?:\s+{_U})?|mười(?:\s+{_U})?|{_D})"
    r"(?=\s+(?:cấp|tỉnh|thành\s+phố|đơn\s+vị|xã|phường|đặc\s+khu|huyện|quận|thị\s+trấn)(?!\w))",
    re.I,
)


def _words_to_int(w: str) -> int:
    t = w.lower().split()
    if t[0] == "mười":
        return 10 + (_DIGIT_WORDS[t[1]] if len(t) > 1 else 0)
    if len(t) > 1:  # "<d> mươi [<u>]"
        return 10 * _DIGIT_WORDS[t[0]] + (_DIGIT_WORDS[t[2]] if len(t) > 2 else 0)
    return _DIGIT_WORDS[t[0]]


def _present_numbers(text: str) -> set[str]:
    """Integers stated as the CURRENT value: dates/resolution numbers removed, Vietnamese
    thousands separators joined ("3.321" -> 3321), and numbers in past clauses dropped
    ("giảm từ 63", "(trước đây là 63)", "từ 63 ... xuống 34")."""
    s = "\n".join(_strip_past(ln) for ln in text.splitlines())
    s = _NUM_WORDS_RE.sub(lambda m: str(_words_to_int(m.group(1))), s)
    s = _THOUSANDS_RE.sub("", s)  # before dates: "1.7.2025" is not joined (4-digit tail)
    s = _DATE_RE.sub(" ", s)
    s = _FROM_TO_RE.sub(" ", s)
    plain = _is_plain(s)
    out = set()
    for m in _NUM_RE.finditer(s):
        clause_start = max(s.rfind(c, 0, m.start()) for c in ",;.\n:")
        ctx = s[clause_start + 1 : m.start()]
        if _is_past_ctx(ctx, plain):
            continue
        out.add(m.group(0).lstrip("0") or "0")
    return out


# scoring ----------------------------------------------------------------------


def _address_view(line: str, plain: bool) -> str:
    line = _UNIT_HYPHEN_RE.get(plain).sub(", ", line)
    return _strip_past(line)


def _score_address(
    pred: str, gold: list[_Target], old: list[_Target], legacy: list[_Target], soft: list[_Target], nodiac: bool
) -> tuple[str, str | None]:
    """Multi-segment golds ("Phường Sài Gòn, Thành phố Hồ Chí Minh")."""
    plain = _is_plain(pred)
    v = _address_view(pred, plain)
    tails = _relation_tails(v, _REL_TRANSFORM)
    cands = tails or [v]
    cands = [_MEMBER_RE.get(plain).sub(", ", c).strip(" ,") for c in cands]

    def any_match(tg: list[_Target], **kw: Any) -> str | None:
        for c in cands:
            d = _match(c, tg, nodiac=nodiac, **kw)
            if d:
                return d
        return None

    g, o, lg = any_match(gold), any_match(old), any_match(legacy)
    if g and not (o or lg):
        return "correct", ("relation" if tails else g)
    if (o or lg) and not g:
        return "outdated", ("legacy_name" if lg and not o else ("relation" if tails else o))
    if g:
        return "other_wrong", "ambiguous"
    # new ward + new province but an abolished district in between
    for c in cands:
        segs = _segments(c)
        kept = [x for i, x in enumerate(segs) if i in (0, len(segs) - 1) or admin_level(x) not in ("D", "C")]
        if len(kept) < len(segs) and _match(", ".join(kept), gold, nodiac=nodiac):
            return "other_wrong", "extra_district"
    if any_match(soft):
        return "other_wrong", "soft_alias"
    if any_match(gold, check_levels=False):
        return "other_wrong", "level_mismatch"
    # only the ward, no province
    for c in cands:
        if len(_segments(c)) == 1 and any(
            len(t.segs) > 1 and _match(c, [_Target([t.segs[0]], [t.nodiac[0]], [t.levels[0]], [t.strict_prefix[0]])],
                                       nodiac=nodiac, first=False)
            for t in gold
        ):
            return "other_wrong", "partial"
    return "other_wrong", None


def _score_short_core(item: dict, raw: str | None, nodiac: bool) -> tuple[str, str | None, str]:
    """Return (label, match_detail, parsed)."""
    pred = _clean_short(raw)
    plain = _is_plain(pred)
    gold_surfaces = _as_list(item.get("answer")) + _as_list(item.get("answer_aliases"))
    gold = _make_targets(gold_surfaces)
    old_surfaces = _as_list(item.get("old_answer"))
    if not old_surfaces and any(len(t.segs) > 1 for t in gold):
        # T4 items whose two-level address is unchanged carry no old_answer; the pre-reform
        # three-level address ("Xã Ia Chia, Huyện Ia Grai, Tỉnh Gia Lai") is still the stale
        # form, as it is for changed items (its district-less variant equals the gold and
        # is dropped below).
        old_surfaces = _as_list((item.get("meta") or {}).get("old_address"))
    old = _drop_same_as_gold(_old_targets(old_surfaces), gold, nodiac)
    legacy = _make_targets(gold_surfaces, _LEGACY)
    soft = _make_targets(gold_surfaces, _SOFT)
    full_text = expand_abbreviations(clean_output(raw))

    def m(p: str, tg: list[_Target], **kw: Any) -> str | None:
        return _match(p, tg, nodiac=nodiac, **kw)

    # reasoning first, then the answer alone on the last line: that line is scored, and
    # the explanation above it (its hedges, the names it echoes, an echoed first line) is not
    gold_levels = [lv for t in gold for lv in t.levels]
    final = _final_line(raw, gold_levels)
    if final is not None:
        pred, plain = final, _is_plain(final)
        if m(pred, gold, first=False):
            return "correct", m(pred, gold, first=False), pred
        if m(pred, old, first=False):
            return "outdated", m(pred, old, first=False), pred
        if m(pred, legacy, first=False):
            return "outdated", "legacy_name", pred

    # 1. whole answer line == a name
    if m(pred, gold, first=False):
        return "correct", m(pred, gold, first=False), pred
    if m(pred, old, first=False):
        return "outdated", m(pred, old, first=False), pred
    if m(pred, legacy, first=False):
        return "outdated", "legacy_name", pred

    if not pred:
        return "invalid", "empty", pred
    if _ABSTAIN_RE.get(plain).search(pred):
        return "invalid", "abstain", pred

    # 2. numeric golds (e.g. T0 "34"): integers stated as the current value.
    gold_num = [normalize_text(x) for x in gold_surfaces if normalize_text(x).isdigit()]
    if gold_num and normalize_text(gold_surfaces[0]).isdigit():
        nums = _present_numbers(full_text)
        gset = {x.lstrip("0") or "0" for x in gold_num}
        g = bool(gset & nums)
        olds = {normalize_text(x).lstrip("0") or "0" for x in _as_list(item.get("old_answer")) if normalize_text(x).isdigit()}
        o = bool((olds - gset) & nums)
        if g and not o:
            return "correct", "numeric", pred
        if o and not g:
            return "outdated", "numeric", pred
        return "other_wrong", ("ambiguous" if g else "numeric"), pred

    # 3. addresses / multi-segment golds
    if any(len(t.segs) > 1 for t in gold):
        lab, d = _score_address(pred, gold, old, legacy, soft, nodiac)
        return lab, d, pred

    p = _strip_past(pred)
    old_all = old + legacy
    # a committed answer (the last line, or a first sentence that is a bare name or
    # address) is scored alone: the explanation around it echoes the question and hedges
    committed = final is not None or _answer_form(_first_sentence(pred), gold_levels)
    if final is not None:
        rest = p
    elif committed:
        rest = _strip_past(_drop_prose_parens(_first_sentence(pred)))
    else:
        rest = "\n".join(_strip_past(ln) for ln in full_text.splitlines())
    abstains = not committed and _abstains(full_text)

    # 4. sentence with relation clauses: score only the present-tense tails
    tails = _relation_tails(p)
    if tails:
        g = any(m(t, gold) for t in tails)
        o = any(m(t, old) or m(t, legacy) for t in tails)
        if g and not o:
            return "correct", "relation", pred
        if o and not g:
            leg = any(m(t, legacy) for t in tails) and not any(m(t, old) for t in tails)
            return "outdated", ("legacy_name" if leg else "relation"), pred
        if g and o:
            return "other_wrong", "ambiguous", pred
        # a tail naming another unit at the gold's level is the committed answer ("Xã Nậm
        # Xé thuộc xã Văn Bàn"): the subject before the verb is the question echoed
        named = [t for t in tails if _names_unit(_first_segment(t), gold_levels)]
        if any(not _contained_text(t, gold, nodiac) for t in named):
            return "other_wrong", "relation", pred
        # From here on a name is only found inside a sentence (an echo of the question as
        # often as an answer): an output that says it does not know is an abstention,
        # unless a clause names one unit ("X hiện thuộc xã Y mới. Tôi không chắc chắn."); a
        # clause listing several ("các xã hiện hành là xã A, xã B, xã C") names no answer
        if abstains and not any(sum(_names_unit(x, gold_levels) for x in _segments(t)) == 1 for t in named):
            return "invalid", "abstain", pred
        if ALLOW_CONTAINMENT:
            g, o = _contained_gold_old(" , ".join(tails), gold, old_all, nodiac)
            if g and not o:
                return "correct", "relation_contained", pred
            if o and not g:
                return "outdated", "relation_contained", pred
            if g and o:
                return "other_wrong", "ambiguous", pred
        # the subject before the verb equals the gold ("Phường Sài Gòn là phường mới thành lập")
        subj = _REL.get(plain).split(p, maxsplit=1)[0]
        if m(subj, gold, first=True):
            return "correct", "subject_segment", pred
        if m(p, soft) or any(m(t, soft) for t in tails):
            return "other_wrong", "soft_alias", pred
        if any(m(t, gold, check_levels=False) for t in tails):
            strict = any(any(t.strict_prefix) for t in gold)
            return "other_wrong", ("ambiguous_province_name" if strict else "level_mismatch"), pred
        return "other_wrong", "relation", pred

    # 5. first segment ("X, Y" lists); the other name anywhere else -> ambiguous, in
    #    whichever order the two names come.
    #    Only the answer line is checked here (explanations often mention the old name).
    #    The first segment of a prose line ("Xã X, huyện Y không được xác nhận trong thông
    #    tin mà tôi có") is the question echoed when the output says it does not know, and
    #    so is a name found only inside the explanation (step 6).
    if abstains:
        return "invalid", "abstain", pred
    d = m(p, gold)
    if d:
        if ALLOW_CONTAINMENT and _contained_gold_old(p, gold, old_all, nodiac)[1]:
            return "other_wrong", "ambiguous", pred
        return "correct", d, pred
    for tg, is_old in ((old, True), (legacy, False)):
        d = m(p, tg)
        if d:
            if ALLOW_CONTAINMENT and _contained_gold_old(p, gold, old_all, nodiac)[0]:
                return "other_wrong", "ambiguous", pred
            return "outdated", (d if is_old else "legacy_name"), pred

    # 6. containment fallback on the whole output (past clauses removed), or on the
    #    committed line alone
    if ALLOW_CONTAINMENT:
        g, o = _contained_gold_old(rest, gold, old_all, nodiac)
        if g and not o:
            return "correct", "contained", pred
        if o and not g:
            return "outdated", "contained", pred
        if g and o:
            return "other_wrong", "ambiguous", pred

    if m(p, soft):
        return "other_wrong", "soft_alias", pred
    if m(p, gold, check_levels=False):
        strict = any(any(t.strict_prefix) for t in gold)
        return "other_wrong", ("ambiguous_province_name" if strict else "level_mismatch"), pred
    return "other_wrong", None, pred


def score_address_components(item: dict, raw: str | None) -> dict[str, str] | None:
    """Score the ward and the province of a T4 address answer separately.

    Needs ``meta.gold_ward`` and ``meta.gold_province`` (full names); old names come from
    ``meta.old_ward_name`` (+ ``meta.old_ward_name_alt``) and ``meta.old_province_name``.
    Same preprocessing as :func:`_score_address` (answer line, past clauses dropped, "X nay
    là Y" -> Y, "thuộc" as separator). Province = the last segment; ward = the first
    ward-level segment (phường/xã/thị trấn/đặc khu), else the segment before the province.
    Labels per component: correct / outdated (matches the old name, which differs from the
    gold) / other_wrong / invalid (empty or abstention). For ``has_diacritics == False``
    items matching is diacritic-insensitive, as for the main label.
    """
    m = item.get("meta") or {}
    if not m.get("gold_ward") or not m.get("gold_province"):
        return None
    nodiac = m.get("has_diacritics") is False
    pred = _final_line(raw, ["W", "P"]) or _clean_short(raw)
    plain = _is_plain(pred)
    if not pred or _ABSTAIN_RE.get(plain).search(pred):
        return {"ward": "invalid", "province": "invalid"}
    v = _address_view(pred, plain)
    tails = _relation_tails(v, _REL_TRANSFORM)
    cand = (tails or [v])[-1]
    cand = _MEMBER_RE.get(plain).sub(", ", cand).strip(" ,")
    segs = _segments(cand)
    if not segs:
        return {"ward": "invalid", "province": "invalid"}

    def lab(seg: str | None, gold: list[str], old: list[str]) -> str:
        if not seg:
            return "other_wrong"
        g = _make_targets(gold)
        o = _drop_same_as_gold(_make_targets(old), g, nodiac)
        if _match(seg, g, nodiac=nodiac, first=False):
            return "correct"
        if _match(seg, o, nodiac=nodiac, first=False):
            return "outdated"
        return "other_wrong"

    prov_seg = segs[-1] if len(segs) > 1 or admin_level(segs[-1]) in ("P", "C") else None
    body = segs[:-1] if prov_seg else segs
    ward_seg = next((x for x in body if admin_level(x) == "W"), None)
    if ward_seg is None and body:
        ward_seg = body[-1]
    old_w = _as_list(m.get("old_ward_name")) + _as_list(m.get("old_ward_name_alt"))
    return {
        "ward": lab(ward_seg, [m["gold_ward"]], old_w),
        "province": lab(prov_seg, [m["gold_province"]], _as_list(m.get("old_province_name"))),
    }


def score_short(item: dict, raw: str | None) -> ScoreResult:
    label, detail, pred = _score_short_core(item, raw, nodiac=False)
    if label == "correct":
        nd_label, nd_detail = label, detail
    else:
        nd_label, nd_detail, _ = _score_short_core(item, raw, nodiac=True)
    res = ScoreResult(pred or None, label, detail, nd_label == "correct", nd_label, label,
                      score_address_components(item, raw))
    if (item.get("meta") or {}).get("has_diacritics") is False:
        # no-diacritic question: the main label is the diacritic-insensitive one
        res.label, res.match_detail = nd_label, (f"nodiac:{nd_detail}" if nd_detail else "nodiac")
    return res


def _old_letter(item: dict) -> str | None:
    old = item.get("old_answer")
    choices = item.get("choices") or []
    valid = LETTERS[: len(choices)] if choices else "ABCD"
    if old is None:
        return None
    if isinstance(old, str) and old.strip().upper() in valid and len(old.strip()) == 1:
        return old.strip().upper()
    # old_answer given as text: map to the choice whose normalised text matches
    for s in _as_list(old):
        k = expand_key(normalize_name(s))
        for i, c in enumerate(choices):
            if normalize_name(c) in k:
                return valid[i]
    return None


def score_mcq(item: dict, raw: str | None) -> ScoreResult:
    choices = item.get("choices") or []
    letter, how = extract_letter(raw, choices)

    def R(label: str, parsed: str | None, detail: str | None) -> ScoreResult:
        # letter extraction does not depend on diacritics: nodiac label == label
        return ScoreResult(parsed, label, detail, label == "correct", label, label)

    if letter is None:
        return R("invalid", None, how)
    gold = str(item["answer"]).strip().upper()
    if letter == gold:
        return R("correct", letter, how)
    if letter == _old_letter(item):
        return R("outdated", letter, how)
    # a distractor that is a legacy name of the gold choice (e.g. "Thừa Thiên Huế")
    idx_gold, idx_pred = LETTERS.find(gold), LETTERS.find(letter)
    if 0 <= idx_gold < len(choices) and 0 <= idx_pred < len(choices):
        leg = _expand_with(normalize_name(choices[idx_gold]), _LEGACY)
        if normalize_name(choices[idx_pred]) in leg:
            return R("outdated", letter, "legacy_name")
    return R("other_wrong", letter, how)


def score(item: dict, raw: str | None) -> ScoreResult:
    if item.get("format") == "mcq":
        return score_mcq(item, raw)
    return score_short(item, raw)
