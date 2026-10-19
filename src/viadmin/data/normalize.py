"""Vietnamese name normalisation helpers used by the data build."""

from __future__ import annotations

import re
import unicodedata

# Combining tone marks (thanh điệu). Vowel-quality marks (circumflex U+0302,
# breve U+0306, horn U+031B) are NOT tone marks and are kept in place.
_TONES = {"̀", "́", "̃", "̉", "̣"}

_WS = re.compile(r"\s+")


def nfc(s: str | None) -> str:
    """NFC-normalise, replace NBSP/zero-width chars, unify apostrophes, collapse whitespace."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFC", str(s))
    s = s.replace("\u00a0", " ").replace("\u200b", "")
    # apostrophe variants -> ASCII apostrophe, e.g. "Cư M\u2019gar" -> "Cư M'gar"
    for ch in ("\u2019", "\u2018", "\u02bc", "`"):
        s = s.replace(ch, "'")
    return _WS.sub(" ", s).strip()


def loose_key(s: str) -> str:
    """Diacritic-, case-, hyphen- and punctuation-insensitive key. Only used to *match*
    a name to a code / record; never used to decide that two names are identical."""
    s = strip_diacritics(s).lower()
    s = re.sub(r"[-\u2013.,'()]", " ", s)
    return _WS.sub(" ", s).strip()


def name_key(s: str) -> str:
    """Comparison key that is insensitive to case, whitespace, tone-mark *placement*
    (e.g. "Hòa" vs "Hoà", "Thủy" vs "Thuỷ") and hyphen spacing, but still sensitive
    to which tones occur ("Hòa" != "Hóa")."""
    s = nfc(s).lower().replace("–", "-")
    s = re.sub(r"\s*-\s*", "-", s)
    def _word(m: re.Match) -> str:
        decomposed = unicodedata.normalize("NFD", m.group(0))
        base = "".join(ch for ch in decomposed if ch not in _TONES)
        tones = "".join(sorted(ch for ch in decomposed if ch in _TONES))
        return unicodedata.normalize("NFC", base) + tones

    # tones are moved to the end of each run of letters (punctuation stays outside)
    return re.sub(r"[^\W\d_]+", _word, s)


def strip_diacritics(s: str) -> str:
    s = unicodedata.normalize("NFD", nfc(s))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D")


_WARD_PREFIXES = [("thị trấn", "thị trấn"), ("phường", "phường"), ("xã", "xã"), ("đặc khu", "đặc khu")]
_DISTRICT_PREFIXES = [("thành phố", "thành phố"), ("thị xã", "thị xã"), ("quận", "quận"), ("huyện", "huyện")]
_PROVINCE_PREFIXES = [("thành phố", "thành phố"), ("tỉnh", "tỉnh"), ("thủ đô", "thành phố")]


def _split(full: str, prefixes) -> tuple[str, str]:
    full = nfc(full)
    low = full.lower()
    for p, t in prefixes:
        if low.startswith(p + " "):
            return t, full[len(p) + 1 :].strip()
    raise ValueError(f"cannot determine unit type of {full!r}")


def split_ward(full: str) -> tuple[str, str]:
    """'Phường Trúc Bạch' -> ('phường', 'Trúc Bạch')."""
    return _split(full, _WARD_PREFIXES)


def split_district(full: str) -> tuple[str, str]:
    return _split(full, _DISTRICT_PREFIXES)


def split_province(full: str) -> tuple[str, str]:
    return _split(full, _PROVINCE_PREFIXES)
