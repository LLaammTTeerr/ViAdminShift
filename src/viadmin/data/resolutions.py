"""Plain-text access to the 34 UBTVQH15 ward-level resolutions (NQ 1654..1687/NQ-UBTVQH15).

Source: reproductions on hoatieu.vn saved under data/raw/ubtvqh_resolutions_hoatieu/html/
(see SOURCE.md). The HTML is parsed as data only (stdlib HTMLParser); nothing is executed.

Only used as a *checking* source by the build: to pick the resolution's spelling of old ward
names and to verify individual pairs. Clause text is lightly repaired because the reproduction
glues some words together ("Phong Quangthành", "Anvà").
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path

from viadmin.data.normalize import name_key, nfc

ROOT = Path(__file__).resolve().parents[3]
RES_DIR = ROOT / "data" / "raw" / "ubtvqh_resolutions_hoatieu" / "html"


class _Text(HTMLParser):
    BLOCK = {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "td"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_to_text(html: str) -> str:
    p = _Text()
    p.feed(html)
    t = unicodedata.normalize("NFC", "".join(p.out))
    t = re.sub(r"[ \t\xa0]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t)


_GLUE = re.compile(r"(?<=[^\W\d_])(?=(?:và|thành|sau khi)\s)")


def _repair(c: str) -> str:
    c = nfc(c)
    c = re.sub(r"(?<=[a-zà-ỹđ])(?=(?:xã|phường|thị trấn|đặc khu)\s)", " ", c)  # "thànhphường"
    c = _GLUE.sub(" ", c)                              # "Quangthành" -> "Quang thành"
    c = c.replace("gọilà", "gọi là").replace("Sắp xếptoàn", "Sắp xếp toàn").replace("cácxã", "các xã")
    c = re.sub(r"\b(và|các|xã|trấn|phường)(?=[A-ZĐÀ-Ỹ])", r"\1 ", c)  # "vàTúng Sán", "thị trấnViệt"
    c = re.sub(r"\blà(?=(?:xã|phường|đặc khu))", "là ", c)          # "làđặc khu"
    c = re.sub(r"\b(xã|phường|đặc khu)(?=[A-ZĐÀ-Ỹ])", r"\1 ", c)    # "xãHồng Thái"
    c = re.sub(r"\)(?=[^\s,.;)])", ") ", c)                           # "(thành phố Trà Vinh)thành"
    c = re.sub(r",(?=\S)", ", ", c)
    return re.sub(r"\s+", " ", c)


@lru_cache(maxsize=None)
def article1_clauses(num: str) -> dict[int, str]:
    """{clause number: repaired text} of Điều 1 of NQ <num>/NQ-UBTVQH15."""
    path = RES_DIR / f"{num}.html"
    text = html_to_text(path.read_text(encoding="utf-8"))
    title = re.search(r"Nghị quyết\s+(?:số\s+)?(\d{4})/NQ-UBTVQH15", text)
    assert title and title.group(1) == num, (num, title and title.group(0))
    a = text.find("Điều 1.")
    b = text.find("Điều 2.", a)
    assert a >= 0 and b > a, num
    out: dict[int, str] = {}
    for m in re.finditer(r"^\s*(\d+)\.\s*(.*)$", text[a:b], flags=re.M):
        k = int(m.group(1))
        if k not in out:
            out[k] = _repair(m.group(2))
    return out


def clause_key(text: str) -> str:
    """name_key of a clause, with punctuation turned into separators, padded with spaces, so that
    `" " + name_key(short_name) + " "` can be searched as a whole-word sequence."""
    k = name_key(text)
    k = re.sub(r"[,;.()]", " ", k)
    return " " + re.sub(r"\s+", " ", k).strip() + " "


def target_of(clause: str) -> str | None:
    """Short name of the new unit a clause forms ("... có tên gọi là xã Hồng Thái." -> "Hồng Thái")."""
    m = re.search(r"có tên gọi là\s+(?:xã|phường|đặc khu)\s+(.+?)\s*\.?\s*$", clause, flags=re.I)
    if m:
        return re.sub(r"\s*\(.*$", "", m.group(1)).strip()
    m = re.search(r"^Đổi tên .*? thành (?:xã|phường|đặc khu)\s+(.+?)\s*\.?\s*$", clause, flags=re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"^Sắp xếp .* thành (?:xã|phường|đặc khu)\s+(.+?)\s*\.?\s*$", clause, flags=re.I)
    if m:  # NQ 1655 k.38: "... thành xã Ninh Thạnh Lợi." (no "có tên gọi là")
        return m.group(1).strip()
    return None


def mentions(clause: str, short_name: str) -> bool:
    """Whole-word (name_key) occurrence of an old unit's short name in a clause's source part."""
    src = re.split(r"\bthành (?:xã|phường|đặc khu)(?: mới)? (?:có tên gọi là|\S)", clause, maxsplit=1)[0]
    return (" " + name_key(short_name) + " ") in clause_key(src)


_MODE = re.compile(
    r"(toàn bộ diện tích tự nhiên(?:,| và)? (?:toàn bộ )?quy mô dân số của|toàn bộ diện tích tự nhiên của"
    r"|toàn bộ quy mô dân số của|một phần diện tích tự nhiên(?:,| và)? (?:toàn bộ )?quy mô dân số của"
    r"|một phần diện tích tự nhiên của|một phần diện tích(?:,| và)? quy mô dân số của|một phần quy mô dân số của"
    r"|phần (?:quy mô dân số )?còn lại của|toàn bộ)",
    flags=re.I,
)
_TYPE = re.compile(r"^(?:các\s+)?(xã|phường|thị trấn|đặc khu|huyện|thị xã|thành phố)\s+(?=\S)", flags=re.I)


def clause_items(clause: str) -> list[dict]:
    """Old units named in the source part of a clause: [{type, name, mode, paren}], mode in
    whole|part. `type` is inherited from the previous item when omitted ("các xã A, B và C")."""
    src = re.split(r"\bthành (?:xã|phường|đặc khu)(?: mới)? (?:có tên gọi là|\S)", clause, maxsplit=1)[0]
    src = re.sub(r"^(?:Sắp xếp|Nhập|Đổi tên)\s+", "", src.strip())
    src = re.sub(r"\s*sau khi (?:thực hiện )?(?:sắp xếp|điều chỉnh).*?(?:Điều này|Nghị quyết này)", "", src)
    out: list[dict] = []
    mode, cur_type, one_shot = "whole", None, None
    for part in _MODE.split(src):
        if not part or not part.strip():
            continue
        low = part.strip().lower()
        if _MODE.fullmatch(part.strip()):
            if low.startswith("phần"):      # "phần còn lại của X": applies to X only
                one_shot, mode_before = "part", mode
            else:
                mode = "part" if low.startswith("một phần") else "whole"
            cur_type = None
            continue
        for it in re.split(r",|;|\s+và\s+", part):
            it = it.strip()
            paren = None
            pm = re.search(r"\(([^)]*)\)?", it)
            if pm:
                paren, it = pm.group(1), (it[: pm.start()] + it[pm.end():]).strip()
            it = re.sub(r"^và\s+", "", it)
            tm = _TYPE.match(it)
            if tm:
                cur_type, it = tm.group(1).lower(), it[tm.end():].strip()
            elif re.match(r"^Phường\s+\S", it):          # "Phường 1", "Phường Đúc" written in full
                cur_type = "phường"
                it = it.split(None, 1)[1] if re.match(r"^Phường\s+(\d+|[IVX]+)$", it) else it
            if it:
                out.append({"type": cur_type, "name": it, "mode": one_shot or mode, "paren": paren})
                if one_shot:
                    one_shot, mode = None, mode_before
    return out


@lru_cache(maxsize=None)
def composition_index(num: str) -> dict[str, tuple[int, str, list[dict]]]:
    """{name_key(new unit short name): (clause no., clause text, items)} for NQ <num>, plus the
    communes kept as-is under the key "__unchanged__" (items parsed from "... không thực hiện sắp
    xếp là các xã A, B")."""
    out: dict[str, tuple[int, str, list[dict]]] = {}
    for k, text in article1_clauses(num).items():
        if "không thực hiện sắp xếp" in text:
            tail = re.split(r"không thực hiện sắp xếp là\s*", text, maxsplit=1)[-1]
            tail = re.sub(r"\.\s*$", "", tail)
            out["__unchanged__"] = (k, text, clause_items(tail))
            continue
        t = target_of(text)
        if t is not None:
            out.setdefault(name_key(t), (k, text, clause_items(text)))
    return out


def clause_for(num: str, new_short_name: str) -> tuple[int, str, list[dict]] | None:
    """The clause of NQ <num> that forms (or keeps) the new unit `new_short_name`."""
    idx = composition_index(num)
    hit = idx.get(name_key(new_short_name))
    if hit is not None:
        return hit
    un = idx.get("__unchanged__")
    if un is not None and any(name_key(i["name"]) == name_key(new_short_name) for i in un[2]):
        return un
    return None
