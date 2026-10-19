"""Text normalisation for answer matching.

Pipeline of :func:`normalize_name` (applied identically to gold and prediction):

1. Unicode NFC, lowercase.
2. Tone-mark placement canonicalisation: "hoà"/"hòa", "thuỷ"/"thủy", "khoẻ"/"khỏe"
   are different code-point sequences even after NFC. We map every
   o+toned(a|e) / u+toned(y) to toned(o|u)+(a|e|y). This is applied symmetrically, so
   it is a canonical form for matching only (it may produce non-standard spellings
   such as "hòang", which is harmless because both sides get the same treatment).
3. "tp." -> "tp ", unit abbreviations "p." / "x." / "q." / "h." / "tx." are expanded
   ("P. Sài Gòn" -> "phường sài gòn", "Q.1" -> "quận 1"; "tt." is NOT expanded because
   "TT. Huế" usually means Thừa Thiên Huế), then every non-word character (punctuation,
   hyphens, dashes) becomes a space; whitespace collapsed.
4. Exactly ONE leading administrative prefix is stripped at a token boundary,
   longest first ("thị xã" before "xã", "thành phố" before "tp"), and only if a
   non-empty remainder is left.
5. All-digit tokens lose leading zeros ("phường 01" -> "1").

Diacritic stripping (:func:`strip_diacritics`) maps "đ"/"Đ" -> "d"/"D" explicitly
(NFD does not decompose đ).
"""

from __future__ import annotations

import re
import unicodedata

# Ordered longest-first (by token count, then length) so multi-word prefixes win.
ADMIN_PREFIXES: tuple[str, ...] = tuple(
    sorted(
        [
            "thành phố",
            "thủ đô",
            "thị trấn",
            "thị xã",
            "đặc khu",
            "tỉnh",
            "tp",
            "phường",
            "xã",
            "quận",
            "huyện",
        ],
        key=lambda p: (-len(p.split()), -len(p)),
    )
)

_TONES = ("̀", "́", "̉", "̃", "̣")  # huyền sắc hỏi ngã nặng


def _build_tone_map() -> dict[str, str]:
    m: dict[str, str] = {}
    for first, second in (("o", "a"), ("o", "e"), ("u", "y")):
        for t in _TONES:
            src = first + unicodedata.normalize("NFC", second + t)
            dst = unicodedata.normalize("NFC", first + t) + second
            m[src] = dst
    return m


_TONE_MAP = _build_tone_map()
_TONE_RE = re.compile("|".join(map(re.escape, _TONE_MAP)))
_NONWORD_RE = re.compile(r"[^\w\s]|_", re.UNICODE)
_WS_RE = re.compile(r"\s+")
_TP_DOT_RE = re.compile(r"\btp\.", re.UNICODE)
# Unit abbreviations with a dot, at a token start, followed by a name or a number.
_ABBR = {"p": "phường", "x": "xã", "q": "quận", "h": "huyện", "tx": "thị xã"}
_ABBR_RE = re.compile(r"(?<![\w.])(tx|p|x|q|h)\.\s*(?=\w)", re.UNICODE | re.IGNORECASE)


def expand_abbreviations(s: str) -> str:
    """"P. Sài Gòn" -> "phường Sài Gòn", "Q.1" -> "quận 1" (case of the rest is kept)."""
    return _ABBR_RE.sub(lambda m: _ABBR[m.group(1).lower()] + " ", s)


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def canon_tone_placement(s: str) -> str:
    """Canonicalise old/new-style tone placement (expects NFC lowercase input)."""
    return _TONE_RE.sub(lambda m: _TONE_MAP[m.group(0)], s)


def normalize_text(s: str | None) -> str:
    """NFC + lowercase + tone canon + punctuation->space + collapse whitespace."""
    if not s:
        return ""
    s = nfc(s).lower()
    s = canon_tone_placement(s)
    s = _TP_DOT_RE.sub("tp ", s)
    s = expand_abbreviations(s)
    s = _NONWORD_RE.sub(" ", s)
    return _WS_RE.sub(" ", s).strip()


def strip_admin_prefix(s: str) -> str:
    """Strip one leading admin prefix from an already ``normalize_text``-ed string."""
    for p in ADMIN_PREFIXES:
        if s.startswith(p + " "):
            rest = s[len(p) + 1 :].strip()
            if rest:
                return rest
    return s


def _strip_leading_zeros(s: str) -> str:
    return " ".join(t.lstrip("0") or "0" if t.isdigit() else t for t in s.split())


def normalize_name(s: str | None) -> str:
    """Full matching normalisation for a single place name (see module doc)."""
    s = normalize_text(s)
    s = strip_admin_prefix(s)
    return _strip_leading_zeros(s)


def strip_diacritics(s: str) -> str:
    """Remove Vietnamese diacritics; 'đ'->'d', 'Đ'->'D'. Result is NFC."""
    s = s.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", s)


def normalize_name_nodiac(s: str | None) -> str:
    """normalize_name followed by diacritic stripping (diacritic-insensitive key).

    If the input already carries diacritics, the prefix is stripped on the
    diacritised form (so "Xã Xà Phìn" -> "xa phin", not "phin"). Only when the input
    has NO diacritics at all (e.g. "Phuong Ben Nghe") is the prefix matched against
    diacritic-free prefixes.
    """
    t = normalize_text(s)
    if t != strip_diacritics(t):
        return strip_diacritics(normalize_name(s))
    for p in ADMIN_PREFIXES:
        q = strip_diacritics(p)
        if t.startswith(q + " ") and t[len(q) + 1 :].strip():
            t = t[len(q) + 1 :].strip()
            break
    return _strip_leading_zeros(t)


def nodiac_keys(s: str | None) -> set[str]:
    """All diacritic-insensitive keys for ``s`` (with and without an extra
    diacritic-free prefix strip), to avoid false negatives such as
    "Quan Lan" (= xã Quan Lạn typed without diacritics) losing "quan"."""
    keys = {normalize_name_nodiac(s), strip_diacritics(normalize_name(s))}
    keys.discard("")
    return keys


# Administrative level implied by an explicit prefix. "thành phố"/"tp" is "C": either a
# centrally-run city (province level) or a provincial city (district level, abolished on
# 1/7/2025) -- compatible with P and D, but NEVER with a ward (W).
_LEVEL = {
    "phường": "W", "xã": "W", "thị trấn": "W", "đặc khu": "W",
    "quận": "D", "huyện": "D", "thị xã": "D",
    "tỉnh": "P", "thủ đô": "P",
    "thành phố": "C", "tp": "C",
}

# (gold level, prediction level) pairs that are compatible. "PC" = no explicit prefix
# but the bare name is a (pre-reform) province name: may be a province or a city.
_COMPATIBLE = {
    ("W", "W"), ("D", "D"), ("P", "P"), ("C", "C"),
    ("C", "D"), ("D", "C"), ("C", "P"), ("P", "C"),
    ("PC", "P"), ("PC", "C"),
}


def levels_compatible(gold_level: str | None, pred_level: str | None) -> bool:
    if not gold_level or not pred_level:
        return True
    return (gold_level, pred_level) in _COMPATIBLE


_PREFIX_TAIL_RES = {
    nodiac: re.compile(
        r"(?:^|\s)(" + "|".join(re.escape(strip_diacritics(p) if nodiac else p) for p in ADMIN_PREFIXES) + r")\s*$"
    )
    for nodiac in (False, True)
}


def preceding_level(hay: str, start: int, nodiac: bool = False) -> str | None:
    """Level of the admin prefix that IMMEDIATELY precedes position ``start`` in a
    ``normalize_text``-ed string (None if the preceding token is not a prefix)."""
    m = _PREFIX_TAIL_RES[nodiac].search(hay[:start])
    if not m:
        return None
    word = m.group(1)
    for p in ADMIN_PREFIXES:
        if word == p or word == strip_diacritics(p):
            return _LEVEL[p]
    return None


def admin_level(s: str | None) -> str | None:
    """'W' (ward level), 'D' (district), 'P' (province), 'C' (thành phố: province or
    district) or None (no prefix)."""
    t = normalize_text(s)
    for p in ADMIN_PREFIXES:
        if t.startswith(p + " ") and t[len(p) + 1 :].strip():
            return _LEVEL[p]
    if t == strip_diacritics(t):  # diacritic-free input, e.g. "Phuong Ben Nghe"
        for p in ADMIN_PREFIXES:
            q = strip_diacritics(p)
            if t.startswith(q + " ") and t[len(q) + 1 :].strip():
                return _LEVEL[p]
    return None
