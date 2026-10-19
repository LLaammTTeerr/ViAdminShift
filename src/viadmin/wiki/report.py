"""Coverage statistics for data/wiki/passages.jsonl (used to write docs/wiki_report.md).

    uv run python -m viadmin.wiki.report [--passages data/wiki/passages.jsonl] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from .api import ROOT

PROCESSED = ROOT / "data" / "processed"
REFORM_KW = re.compile(r"(sáp nhập|hợp nhất|sắp xếp|giải thể|kết thúc hoạt động|chấm dứt hoạt động|"
                       r"tỉnh mới|chính quyền địa phương hai cấp|hai cấp|không còn tồn tại|"
                       r"không tổ chức cấp huyện|cấp huyện)", re.I)
FORMER_RE = re.compile(
    r"\blà (một )?(tỉnh|huyện|quận|thị xã|thành phố|đơn vị hành chính)( [^\s,.;]+){0,3} cũ\b|"
    r"34 (đơn vị hành chính cấp tỉnh|tỉnh)|202/2025/QH15|"
    r"\b0?1 tháng 0?7 năm 2025|\b0?1/0?7/2025|nay là một phần của|nay tương ứng với", re.I)
# Wider "former unit" phrasing (review): any descriptive words between the unit type and
# "cũ" up to the next comma/period ("là một huyện miền núi biên giới cũ") but not across
# tỉnh/thuộc/của/từng, so historical "là một huyện thuộc tỉnh Cần Thơ cũ" / "là tỉnh lỵ của tỉnh
# Kiến Tường cũ" do not count; "<X> trước đây là <unit>" at the start of a line (not inside a
# parenthesis: "Huế (trước đây là tỉnh Thừa Thiên Huế)"), "<X> cũ là <unit>" at the start of a line
# ("Đăk Hà cũ là một huyện"), and "là (một) đặc khu".
FORMER_WIDE_RE = re.compile(
    r"\blà (một )?(tỉnh|huyện|quận|thị xã|thành phố|đơn vị hành chính|đặc khu)\b"
    r"(?:(?!\b(?:tỉnh|thuộc|của|từng)\b)[^,.;\n]){0,80}?\bcũ\b|"
    r"^[^.(\n]{0,80}?\btrước đây là (một )?(tỉnh|huyện|quận|thị xã|thành phố)\b|"
    r"^[^.(\n]{1,40}? cũ là (một )?(tỉnh|huyện|quận|thị xã|thành phố)\b|"
    r"\blà (một )?đặc khu\b", re.I | re.M)
NEW_DIVISION_RE = re.compile(r"Phân chia hành chính: ([^\n]*)")


def describes_new_divisions(row: dict) -> bool:
    """Infobox 'Phân chia hành chính' lists only commune-level units (phường/xã/đặc khu)."""
    m = NEW_DIVISION_RE.search(row.get("infobox_text") or "")
    if not m:
        return False
    v = m.group(1).lower()
    return bool(re.search(r"phường|xã|đặc khu", v)) and not re.search(r"huyện|quận|thị xã|thị trấn", v)


def mentions_reform(text: str, wide: bool = True) -> bool:
    """A sentence that combines '2025' with a restructuring keyword, or an explicit
    'former unit' / '34 provinces' / Resolution 202/2025/QH15 phrase. `wide=False` is the strict
    (lower-bound) detector; the default also accepts FORMER_WIDE_RE phrasings (upper bound)."""
    if FORMER_RE.search(text) or (wide and FORMER_WIDE_RE.search(text)):
        return True
    for sent in re.split(r"(?<=[.!?])\s+|\n", text):
        if re.match(r"^[^:.]{1,60}: ", sent):   # infobox "key: value" line
            continue
        if "2025" in sent and REFORM_KW.search(sent):
            return True
    return False


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


_TONED = {"a": "àáảãạ", "e": "èéẻẽẹ", "y": "ỳýỷỹỵ"}
_BASE_TONE = {"o": "òóỏõọ", "u": "ùúủũụ"}


def canon(s: str) -> str:
    """Comparison form: NFC, unified dashes, and tone mark moved to the first vowel of a
    word-final oa/oe/uy cluster ("Hoá"->"Hóa", "Thuỵ"->"Thụy"). Used only for matching."""
    import unicodedata
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"[ \t]*[‐-―−-][ \t]*", " - ", s)
    def fix(m):
        first, second = m.group(1), m.group(2)
        for base, toned in _TONED.items():
            if second in toned:
                idx = toned.index(second)
                lower = first.lower()
                new_first = _BASE_TONE[lower][idx]
                if first.isupper():
                    new_first = new_first.upper()
                return new_first + base
        return m.group(0)
    return re.sub(r"([oOuU])([àáảãạèéẻẽẹỳýỷỹỵ])(?![\wà-ỹ])", fix, s)


def name_in_text(name: str, text: str) -> bool:
    """Ward name appears as a list item / table cell / comma-separated token in text
    (compared in canon() form)."""
    name, text = canon(name), canon(text)
    pat = (r"(?:^|[\n,;:|(–·-]\s*|\svà\s|(?:phường|xã|thị trấn|đặc khu|Phường|Xã|Đặc khu)\s)"
           + re.escape(name) + r"(?=\s*(?:$|[\n,;|.):·]|\svà\s|\s\())")
    return re.search(pat, text) is not None


def ward_coverage(rows: list[dict], era: str, entity_set: str, ward_table: str,
                  key: str) -> dict[str, tuple[int, int]]:
    """For each entity: (#gold ward names found in admin_text, #gold wards)."""
    wards = load(PROCESSED / ward_table)
    by_parent: dict[str, list[str]] = defaultdict(list)
    for w in wards:
        by_parent[w[key]].append(w.get("short_name") or w["name"])
    out = {}
    for r in rows:
        if r["era"] != era or r["entity_set"] != entity_set or not r.get("entity_code"):
            continue
        gold = by_parent.get(r["entity_code"], [])
        txt = r.get("admin_text") or ""
        found = sum(1 for n in gold if name_in_text(n, txt))
        out[r["passage_id"]] = (found, len(gold))
    return out


def stats(rows: list[dict]) -> dict:
    s: dict = {}
    sets = Counter((r["entity_set"], r["era"]) for r in rows)
    s["counts"] = {f"{k[0]}/{k[1]}": v for k, v in sorted(sets.items())}
    s["admin_text_present"] = {f"{k[0]}/{k[1]}": sum(1 for r in rows if (r["entity_set"], r["era"]) == k
                                                     and r.get("admin_text")) for k in sorted(sets)}
    s["reform_mention"] = {}
    for es in ("old_province", "new_province", "old_district"):
        for era in ("old", "new"):
            sub = [r for r in rows if r["entity_set"] == es and r["era"] == era]
            if not sub:
                continue
            s["reform_mention"][f"{es}/{era}"] = {
                "n": len(sub),
                "in_text_strict": sum(1 for r in sub if mentions_reform(r["text"], wide=False)),
                "in_text": sum(1 for r in sub if mentions_reform(r["text"])),
                "in_text_or_admin": sum(1 for r in sub if mentions_reform(
                    r["text"] + "\n" + (r.get("admin_text") or ""))),
                "infobox_lists_only_communes": sum(1 for r in sub if describes_new_divisions(r)),
            }
    s["ward_cov_new_province_new"] = ward_coverage(rows, "new", "new_province", "wards_new.jsonl",
                                                   "province_code")
    s["ward_cov_old_district_old"] = ward_coverage(rows, "old", "old_district", "wards_old.jsonl",
                                                   "district_code")
    return s


def summarize_cov(cov: dict[str, tuple[int, int]], thresholds=(0.9, 0.5)) -> dict:
    n = len(cov)
    res = {"n": n}
    for t in thresholds:
        res[f">={int(t * 100)}%"] = sum(1 for f, g in cov.values() if g and f / g >= t)
    res["none"] = sum(1 for f, g in cov.values() if f == 0)
    tot_f = sum(f for f, _ in cov.values())
    tot_g = sum(g for _, g in cov.values())
    res["micro_recall"] = round(tot_f / tot_g, 3) if tot_g else None
    return res


def stated_commune_count(row: dict) -> int | None:
    """'<Name> có N đơn vị hành chính cấp xã' in admin_text (None if not stated)."""
    name = re.escape(row["entity_name"])
    m = re.search(name + r"\s+có\s+(\d+)\s+đơn vị hành chính cấp xã", row.get("admin_text") or "")
    return int(m.group(1)) if m else None


_LIST_SENT_RE = re.compile(r"có\s+\d+\s+đơn vị hành chính cấp xã[^.\n]*")
_LIST_GROUP_RE = re.compile(r"(?:\d+\s+)?(?:các\s+)?(?:phường|xã|thị trấn)\s*:\s*(.*?)"
                            r"(?=\s+và\s+\d+\s+(?:phường|xã|thị trấn)|\s+với\s|;|$)")
_SEAT_RE = re.compile(r"thị trấn\s+([A-ZĐÀ-Ỹ][^\s,(]*(?:\s+[A-ZĐÀ-Ỹ0-9][^\s,(]*)*)\s*\(huyện lỵ\)")
_NAME_TOKEN_RE = re.compile(r"^[A-ZĐÀ-Ỹ0-9][\w'’\-]*(?:\s+[A-ZĐÀ-Ỹ0-9][\w'’\-]*){0,4}$")


def listed_commune_names(admin_text: str | None) -> list[str]:
    """Commune names enumerated in the '<X> có N đơn vị hành chính cấp xã ..., bao gồm ...' sentence
    of an (old-era district) admin section; [] if there is no such sentence."""
    m = _LIST_SENT_RE.search(admin_text or "")
    if not m:
        return []
    sent = re.sub(r"\([^()]*\)", lambda x: x.group(0) if "huyện lỵ" in x.group(0) else "", m.group(0))
    names = [x.group(1) for x in _SEAT_RE.finditer(sent)]
    for g in _LIST_GROUP_RE.finditer(sent):
        for n in re.split(r",\s*|\s+và\s+", g.group(1)):
            n = re.sub(r"\s*\(huyện lỵ\)", "", n).strip(" .")
            if _NAME_TOKEN_RE.match(n):
                names.append(n)
    return list(dict.fromkeys(names))


def _loose(name: str) -> str:
    from viadmin.data.normalize import name_key
    return re.sub(r"[\s\-'’]", "", name_key(name))


def _gold_old_names_by_district() -> dict[str, set[str]]:
    by: dict[str, set[str]] = defaultdict(set)
    for w in load(PROCESSED / "wards_old.jsonl"):
        by[w["district_code"]].add(_loose(w.get("short_name") or w["name"]))
        if w.get("name_alt"):
            by[w["district_code"]].add(_loose(re.sub(r"^(Phường|Xã|Thị trấn)\s+", "", w["name_alt"])))
    return by


def text_similarity(a: str, b: str) -> float:
    import difflib
    return round(difflib.SequenceMatcher(None, a, b, autojunk=False).ratio(), 3)


COMMUNE_TYPES = {"phường", "xã", "đặc khu", "thị trấn"}


def quality_rows(rows: list[dict]) -> list[dict]:
    """Per-passage consistency of admin_text with the canonical tables (for the generator)."""
    s = stats(rows)
    cov = {**s["ward_cov_new_province_new"], **s["ward_cov_old_district_old"]}
    gold_old = _gold_old_names_by_district()
    by_id = {r["passage_id"]: r for r in rows}
    out = []
    for r in rows:
        q = {"passage_id": r["passage_id"], "entity_set": r["entity_set"], "era": r["era"],
             "mentions_reform": mentions_reform(r["text"] + "\n" + (r.get("admin_text") or "")),
             "mentions_reform_strict": mentions_reform(r["text"] + "\n" + (r.get("admin_text") or ""),
                                                       wide=False),
             "stated_commune_count": stated_commune_count(r)}
        if r["passage_id"] in cov:
            f, g = cov[r["passage_id"]]
            q.update({"gold_wards": g, "gold_wards_named_in_admin_text": f,
                      "stated_count_matches_gold": (q["stated_commune_count"] == g)
                      if q["stated_commune_count"] is not None else None})
        if r["entity_set"] == "old_district" and r["era"] == "old" and r.get("entity_code"):
            listed = listed_commune_names(r.get("admin_text"))
            gold = gold_old.get(r["entity_code"], set())
            q["admin_listed_names"] = len(listed)
            q["admin_names_not_in_gold"] = [n for n in listed if _loose(n) not in gold]
        if r["era"] == "new":
            other = by_id.get(r["passage_id"][:-len("new")] + "old")
            sim = text_similarity(other["text"], r["text"]) if other else None
            q["text_similarity_to_old"] = sim
            # The passage's `text` (lead + key infobox facts, the default passage body) shows the
            # post-reform state: it says so in words, or the page now describes the replacing
            # commune-level unit, or (provinces) the infobox lists only phường/xã/đặc khu.
            # admin_text is NOT used: old-era district admin sections already mention the
            # 2025-01-01 commune mergers ("năm 2025 ... sáp nhập", 37/694 old passages).
            q["new_text_reflects_reform"] = bool(
                mentions_reform(r["text"]) or (r.get("lead_subject_type") in COMMUNE_TYPES)
                or (r["entity_type"] == "province" and describes_new_divisions(r)))
        out.append(q)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--passages", default=str(ROOT / "data" / "wiki" / "passages.jsonl"))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write-quality", action="store_true",
                    help="write data/wiki/quality.jsonl next to the passages file")
    a = ap.parse_args(argv)
    rows = load(Path(a.passages))
    if a.write_quality:
        out = Path(a.passages).parent / "quality.jsonl"
        with out.open("w", encoding="utf-8") as f:
            for q in quality_rows(rows):
                f.write(json.dumps(q, ensure_ascii=False) + "\n")
        print("wrote", out)
    s = stats(rows)
    if a.json:
        print(json.dumps(s, ensure_ascii=False, indent=1))
        return
    for k in ("counts", "admin_text_present", "reform_mention"):
        print(k, json.dumps(s[k], ensure_ascii=False, indent=1))
    print("ward coverage new provinces (new era):", summarize_cov(s["ward_cov_new_province_new"]))
    print("ward coverage old districts (old era):", summarize_cov(s["ward_cov_old_district_old"]))


if __name__ == "__main__":
    main()
