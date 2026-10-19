"""Entity lists (old/new provinces, old districts) taken from Vietnamese Wikipedia list pages.

Sources (exact revisions, so the lists are reproducible):
* old provinces (63): "Đơn vị hành chính cấp tỉnh (Việt Nam)" rev 73531195 (2025-05-23), table
  under "Danh sách tỉnh thành".
* new provinces (34): same page rev 75581808 (2026-09-23), table under "Danh sách".
  Only the names / link titles are used (names are unchanged since 2025-07-01; the 2026 table marks
  Đồng Nai, Quảng Ninh, Bắc Ninh as centrally-run cities, which we do NOT use here).
* old districts (696): "Danh sách đơn vị hành chính cấp huyện của Việt Nam" rev 73518904
  (2025-05-18), tables under "Danh sách các đơn vị hành chính cấp huyện".
The link *targets* (hrefs) are titles as written in the old wikitext; they are resolved
historically in fetch.py (page moves/redirects after the cut-off are followed via the move log).
"""
from __future__ import annotations

import unicodedata
from dataclasses import asdict, dataclass
from urllib.parse import unquote

from .api import WikiClient
from .text import Node, _content_root, _heading_of, inline_text, parse_html

PROVINCE_LIST_TITLE = "Đơn vị hành chính cấp tỉnh (Việt Nam)"
PROVINCE_LIST_OLD_REV = 73531195
PROVINCE_LIST_NEW_REV = 75581808
DISTRICT_LIST_TITLE = "Danh sách đơn vị hành chính cấp huyện của Việt Nam"
DISTRICT_LIST_OLD_REV = 73518904

# centrally-run cities as of 2025-01-01 .. 2025-06-30 (Huế since 2025-01-01)
OLD_CITIES = {"Hà Nội", "Thành phố Hồ Chí Minh", "Hải Phòng", "Đà Nẵng", "Cần Thơ", "Huế"}


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip()


@dataclass
class Entity:
    entity_set: str          # "old_province" | "new_province" | "old_district"
    entity_type: str         # "province" | "district"
    name: str                # name as displayed in the list (NFC)
    link_title: str          # wiki title linked from the list (historical, as in old wikitext)
    parent_name: str | None = None   # districts: old province name
    subtype: str | None = None       # districts: huyện | quận | thị xã | thành phố | huyện đảo

    def to_dict(self) -> dict:
        return asdict(self)


def _href_title(a: Node) -> str | None:
    href = a.attrs.get("href", "")
    if href.startswith("/wiki/"):
        return nfc(unquote(href[len("/wiki/"):]).replace("_", " ").split("#")[0])
    if "title=" in href and "redlink=1" in href:
        t = href.split("title=", 1)[1].split("&", 1)[0]
        return nfc(unquote(t).replace("_", " "))
    return None


def _first_link(cell: Node) -> tuple[str, str] | None:
    for n in cell.iter():
        if n.tag == "a":
            t = _href_title(n)
            if t:
                return inline_text(n), t
    return None


def _section_nodes(root: Node, heading: str) -> list[Node]:
    out, cur = [], None
    for ch in root.children:
        if not isinstance(ch, Node):
            continue
        h = _heading_of(ch)
        if h:
            cur = h[1]
            continue
        if cur == heading:
            out.append(ch)
    return out


def _rows(nodes: list[Node]):
    for n in nodes:
        for tr in n.iter():
            if tr.tag == "tr":
                yield [c for c in tr.children if isinstance(c, Node) and c.tag in ("td", "th")]


def old_provinces(client: WikiClient) -> list[Entity]:
    html = client.parse_revision(PROVINCE_LIST_OLD_REV)["text"]
    root = _content_root(parse_html(html))
    out = []
    for cells in _rows(_section_nodes(root, "Danh sách tỉnh thành")):
        if len(cells) < 3 or cells[0].tag != "td":
            continue
        if not inline_text(cells[0]).isdigit():
            continue
        link = _first_link(cells[1])
        if link:
            out.append(Entity("old_province", "province", nfc(link[0]), link[1]))
    return out


def new_provinces(client: WikiClient) -> list[Entity]:
    html = client.parse_revision(PROVINCE_LIST_NEW_REV)["text"]
    root = _content_root(parse_html(html))
    out = []
    for cells in _rows(_section_nodes(root, "Danh sách")):
        if len(cells) < 3 or not inline_text(cells[0]).isdigit():
            continue
        link = _first_link(cells[1])
        if link:
            name = nfc(link[0])
            if name == "TP. Hồ Chí Minh":
                name = "Thành phố Hồ Chí Minh"
            out.append(Entity("new_province", "province", name, link[1]))
    return out


def old_districts(client: WikiClient) -> list[Entity]:
    html = client.parse_revision(DISTRICT_LIST_OLD_REV)["text"]
    root = _content_root(parse_html(html))
    out = []
    for cells in _rows(_section_nodes(root, "Danh sách các đơn vị hành chính cấp huyện")):
        if len(cells) < 4 or cells[0].tag != "td" or not inline_text(cells[0]).isdigit():
            continue
        link = _first_link(cells[1])
        prov = inline_text(cells[2])
        note = inline_text(cells[3]).lower()
        subtype = note if note in {"quận", "thị xã", "thành phố", "huyện đảo"} else "huyện"
        if link:
            out.append(Entity("old_district", "district", nfc(link[0]), link[1],
                              parent_name=nfc(prov), subtype=subtype))
    return out
