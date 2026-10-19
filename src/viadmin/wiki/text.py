"""Convert MediaWiki-rendered HTML (action=parse output) into clean plain text.

Only the standard library is used (html.parser). The HTML is parsed into a small element tree,
noise (references, navboxes, maintenance boxes, styles, images, edit links, ...) is dropped, and
the remaining content is rendered as text:

* paragraphs / headings / list items / table rows become separate lines;
* table cells are joined with " | " (so ward lists stored in tables survive);
* the infobox is removed from the prose and can be extracted separately as "key: value" lines.

Public API:
    parse_html(html) -> Node
    extract(html) -> PageText(lead, infobox, sections)
    lead_text / admin_section_text helpers, truncate().
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param",
        "source", "track", "wbr"}
BLOCK = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "dl", "dt", "dd",
         "table", "tbody", "thead", "tfoot", "tr", "caption", "blockquote", "pre", "figure",
         "section", "center"}
SKIP_TAGS = {"style", "script", "noscript", "img", "link", "meta", "figure", "audio", "video",
             "math", "svg", "map"}
# class tokens whose element (and subtree) is dropped
SKIP_CLASSES = {
    "reference", "mw-editsection", "hatnote", "ambox", "metadata", "navbox", "navbox-styles",
    "navbox-inner", "vertical-navbox", "mw-references-wrap", "references", "reflist", "refbegin",
    "noprint", "toc", "toccolours", "thumb", "gallery", "mw-gallery-traditional", "sistersitebox",
    "side-box", "portalbox", "mw-cite-backlink", "geo", "geo-dms", "geo-dec", "geo-default",
    "plainlinks-print", "mw-kartographer-maplink", "mw-kartographer-container", "mbox-small",
    "Inline-Template", "printfooter", "catlinks", "mwe-math-element", "mw-empty-elt",
    "infobox",  # rendered separately via extract_infobox
    "tmulti", "thumbinner", "cite-bracket", "mw-collapsible-toggle", "mw-ext-cite-error",
    "error", "shortdescription", "navbar", "dablink", "rellink", "navigation-not-searchable", "authority-control",
}
SKIP_IDS = {"coordinates", "toc", "References", "catlinks"}
HEADING = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}


@dataclass
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["Node | str"] = field(default_factory=list)
    parent: "Node | None" = None

    @property
    def classes(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())

    def iter(self):
        yield self
        for c in self.children:
            if isinstance(c, Node):
                yield from c.iter()


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: (v or "") for k, v in attrs}, parent=self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, {k: (v or "") for k, v in attrs}, parent=self.stack[-1])
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return
        # unmatched end tag: ignore

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse_html(html: str) -> Node:
    b = _TreeBuilder()
    b.feed(html)
    b.close()
    return b.root


NAVBOX_KEEP_RE = re.compile(r"(xã|phường|thị trấn|đặc khu|đơn vị hành chính)", re.I)
NAVBOX_CLASSES = {"navbox", "navbox-inner", "navbox-subgroup", "navbox-styles", "navbox-list",
                  "navbox-group", "navbox-title", "navbox-abovebelow", "navbox-even", "navbox-odd"}


def _navbox_title(node: Node) -> str:
    for n in node.iter():
        if "navbox-title" in n.classes:
            return inline_text(n)
    return ""


def _is_skipped(node: Node, keep_navbox: bool = False) -> bool:
    if keep_navbox and node.classes & NAVBOX_CLASSES and not node.classes & {"navbar"}:
        return False
    if node.tag in SKIP_TAGS:
        return True
    if node.attrs.get("id") in SKIP_IDS:
        return True
    cls = node.classes
    if cls & SKIP_CLASSES:
        return True
    if any(c.startswith(("box-", "navbox", "mw-kartographer")) for c in cls):
        return True
    style = node.attrs.get("style", "").replace(" ", "").lower()
    if "display:none" in style or "position:absolute" in style:  # hidden / map overlay labels
        return True
    if node.attrs.get("role") in {"navigation", "note"} and node.tag != "table":
        return True
    return False


# ---------------------------------------------------------------------------------------------
# rendering
class _Renderer:
    def __init__(self, keep_navbox: bool = False) -> None:
        self.keep_navbox = keep_navbox
        self.lines: list[str] = []
        self.cur: list[str] = []
        self.cell_depth = 0  # >0 while inside a table cell: <br> becomes a space

    def newline(self) -> None:
        line = "".join(self.cur)
        self.cur = []
        line = re.sub(r"[ \t ]+", " ", line).strip()
        line = re.sub(r"\s*\|\s*$", "", line)          # trailing empty cells
        line = re.sub(r"^(\|\s*)+", "", line).strip()   # leading empty cells
        if line:
            self.lines.append(line)

    def text(self, s: str) -> None:
        self.cur.append(s.replace("\n", " "))

    def render(self, node: Node, list_depth: int = 0) -> None:
        for child in node.children:
            if isinstance(child, str):
                self.text(child)
                continue
            if _is_skipped(child, self.keep_navbox):
                continue
            tag = child.tag
            if tag == "br":
                if self.cell_depth:
                    self.text(" ")
                else:
                    self.newline()
                continue
            if tag in ("td", "th"):
                if self.cur and "".join(self.cur).strip():
                    self.text(" | ")
                self.cell_depth += 1
                self.render(child, list_depth)
                self.cell_depth -= 1
                continue
            if tag == "table":
                # a nested table inside a cell starts on its own lines
                saved, self.cell_depth = self.cell_depth, 0
                self.newline()
                self.render(child, list_depth)
                self.newline()
                self.cell_depth = saved
                continue
            if tag == "li":
                self.newline()
                self.text("- ")
                self.render(child, list_depth + 1)
                self.newline()
                continue
            if tag in BLOCK:
                self.newline()
                self.render(child, list_depth)
                self.newline()
                continue
            self.render(child, list_depth)

    def result(self) -> str:
        self.newline()
        return "\n".join(self.lines)


def node_text(node: Node, keep_navbox: bool = False) -> str:
    r = _Renderer(keep_navbox)
    r.render(node)
    return clean_text(r.result())


def inline_text(node: Node) -> str:
    """Single-line text of a node (block breaks become ', ')."""
    t = node_text(node)
    return re.sub(r"\s*\n\s*", ", ", t).strip(" ,")


def clean_text(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = s.replace("​", "").replace("﻿", "").replace("­", "")
    s = re.sub(r"\[\s*(\d+|[a-z]|cần dẫn nguồn|cần chú thích|ghi chú \d+)\s*\]", "", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" +([,.;:!?)])", r"\1", s)
    s = re.sub(r"\( +", "(", s)
    s = re.sub(r"\n{2,}", "\n", s)
    return s.strip()


# ---------------------------------------------------------------------------------------------
# page structure
@dataclass
class Section:
    title: str
    level: int
    text: str
    navbox_text: str = ""   # navboxes inside the section that list communes (admin lists)


@dataclass
class PageText:
    lead: str
    infobox: list[str]
    sections: list[Section]


def _content_root(root: Node) -> Node:
    for n in root.iter():
        if "mw-parser-output" in n.classes:
            return n
    return root


def _heading_of(node: Node) -> tuple[int, str] | None:
    """If node is a heading (or MediaWiki's div.mw-heading wrapper) return (level, title)."""
    if node.tag in HEADING:
        return HEADING[node.tag], inline_text(node)
    if node.tag == "div" and "mw-heading" in node.classes:
        for c in node.children:
            if isinstance(c, Node) and c.tag in HEADING:
                return HEADING[c.tag], inline_text(c)
    return None


def extract_infobox(root: Node) -> list[str]:
    """First infobox as 'key: value' lines (header rows prefix their following labels)."""
    box = None
    for n in root.iter():
        if n.tag == "table" and "infobox" in n.classes:
            box = n
            break
    if box is None:
        return []
    lines: list[str] = []
    header = ""
    for tr in box.iter():
        if tr.tag != "tr":
            continue
        cells = [c for c in tr.children if isinstance(c, Node) and c.tag in ("th", "td")]
        if len(cells) == 1 and "infobox-header" in cells[0].classes:
            header = inline_text(cells[0])
            continue
        if len(cells) == 2 and cells[0].tag == "th":
            key = inline_text(cells[0])
            val = inline_text(cells[1])
            if not key or not val:
                continue
            if header and header.lower() not in key.lower():
                key = f"{header} – {key}"
            lines.append(f"{key}: {val}")
    # dedupe, keep order
    seen: set[str] = set()
    out = []
    for ln in lines:
        if ln not in seen:
            seen.add(ln)
            out.append(ln)
    return out


def extract(html: str) -> PageText:
    root = parse_html(html)
    content = _content_root(root)
    infobox = extract_infobox(content)
    # Split top-level children into lead + sections by headings.
    groups: list[tuple[int, str, list[Node | str]]] = [(0, "", [])]
    for child in content.children:
        h = _heading_of(child) if isinstance(child, Node) else None
        if h:
            groups.append((h[0], h[1], []))
        else:
            groups[-1][2].append(child)
    def render(children):
        holder = Node("div", children=children)
        return node_text(holder)
    lead_children = groups[0][2]
    # lead: paragraphs and lists only (drop stray tables such as infobox remnants)
    lead_nodes = [c for c in lead_children if isinstance(c, Node) and c.tag in ("p", "ul", "ol", "dl")]
    lead = render(lead_nodes)
    sections = []
    for lvl, t, ch in groups[1:]:
        boxes = []
        for c in ch:
            if isinstance(c, Node) and "navbox" in c.classes and NAVBOX_KEEP_RE.search(_navbox_title(c)):
                boxes.append(node_text(c, keep_navbox=True))
        sections.append(Section(t, lvl, render(ch), "\n".join(b for b in boxes if b)))
    return PageText(lead=lead, infobox=infobox, sections=sections)


_ADMIN_CORE = r"(các\s+)?(đơn vị\s+|tổ chức\s+|phân chia\s+|phân cấp\s+)?hành ch[íá]nh"
ADMIN_EXACT_RE = re.compile(rf"^{_ADMIN_CORE}(\s+(cấp\s+\w+|trực thuộc|hiện nay|hiện tại))?$", re.I)
ADMIN_RE = re.compile(rf"^{_ADMIN_CORE}", re.I)
ADMIN_ANY_RE = re.compile(r"(đơn vị hành chính|phân chia hành chính|hành chính)", re.I)


def find_admin_section(sections: list[Section]) -> tuple[str, str] | None:
    """Return (heading, text) of the administrative-divisions section incl. its subsections.

    Preference order: (1) a heading that is exactly "(Các) (Đơn vị/Tổ chức/Phân chia) hành chính"
    (possibly a subsection, e.g. "Tổ chức hành chính" under "Tổ chức hành chính và chính quyền");
    (2) a heading starting with such a phrase; (3) any heading containing "hành chính" that is
    not about history ("Lịch sử ...")."""
    def pick(pred):
        for i, s in enumerate(sections):
            title = unicodedata.normalize("NFC", s.title).strip()
            if pred(title):
                parts = [p for p in (s.text, s.navbox_text) if p]
                for sub in sections[i + 1:]:
                    if sub.level <= s.level:
                        break
                    body = "\n".join(p for p in (sub.text, sub.navbox_text) if p)
                    parts.append(f"{sub.title}\n{body}" if body else sub.title)
                text = "\n".join(p for p in parts if p).strip()
                if text:
                    return title, text
        return None
    return (pick(lambda t: bool(ADMIN_EXACT_RE.match(t)))
            or pick(lambda t: bool(ADMIN_RE.match(t)))
            or pick(lambda t: bool(ADMIN_ANY_RE.search(t)) and not t.lower().startswith("lịch sử")))


SOURCE_LINE_RE = re.compile(r"^(Nguồn|Ghi chú|Chú thích)\s*:", re.I)
TEMPLATE_LINE_RE = re.compile(r"^(Bản mẫu|Template)\s*:")   # navbox title/navbar remnants


def tidy_section(text: str) -> str:
    """Drop repeated table-header lines (multi-column layouts), 'Nguồn: ...' trailer lines and
    stray 'Bản mẫu:...' navbox-title lines."""
    out: list[str] = []
    seen_tables: set[str] = set()
    for line in text.split("\n"):
        if SOURCE_LINE_RE.match(line) or TEMPLATE_LINE_RE.match(line):
            continue
        if " | " in line:
            if line in seen_tables:
                continue
            seen_tables.add(line)
        out.append(line)
    return "\n".join(out)


def truncate(s: str, limit: int, at_sentence: bool = True) -> str:
    """Cut to <= limit chars at a line / sentence / word boundary."""
    if len(s) <= limit:
        return s
    cut = s[:limit]
    best = -1
    for sep in ("\n",) + ((". ", "; ") if at_sentence else ()):
        k = cut.rfind(sep)
        if k > limit * 0.6:
            best = max(best, k + (1 if sep != "\n" else 0))
    if best == -1:
        k = cut.rfind(" ")
        best = k if k > limit * 0.6 else limit
    return cut[:best].rstrip()


def is_redirect_html(html: str) -> bool:
    return 'class="redirectMsg"' in html or "redirectMsg" in html[:2000]
