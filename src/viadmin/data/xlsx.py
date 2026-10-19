"""Minimal, dependency-free .xlsx reader (stdlib zipfile + ElementTree).

Only reads cell *values* (shared strings, inline strings, numbers) as text.
The workbook is treated purely as data: no formulas are evaluated, no macros run.
"""

from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _col_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group(0)  # type: ignore[union-attr]
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _text(el: ET.Element) -> str:
    return "".join(t.text or "" for t in el.iter(f"{{{_NS['m']}}}t"))


def read_xlsx(path: str) -> dict[str, list[list[str]]]:
    """Return {sheet_name: rows}, each row a list of cell strings ('' for empty)."""
    with zipfile.ZipFile(path) as zf:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            shared = [_text(si) for si in root.findall("m:si", _NS)]
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {r.get("Id"): r.get("Target") for r in rels}
        out: dict[str, list[list[str]]] = {}
        for sh in wb.find("m:sheets", _NS):  # type: ignore[union-attr]
            name = sh.get("name")
            target = rid_to_target[sh.get(f"{{{_REL_NS}}}id")]
            target = target.lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            root = ET.fromstring(zf.read(target))
            rows: list[list[str]] = []
            for row in root.iter(f"{{{_NS['m']}}}row"):
                cells: dict[int, str] = {}
                for c in row.findall("m:c", _NS):
                    idx = _col_index(c.get("r"))
                    t = c.get("t")
                    if t == "s":
                        v = c.find("m:v", _NS)
                        val = shared[int(v.text)] if v is not None and v.text else ""
                    elif t == "inlineStr":
                        is_ = c.find("m:is", _NS)
                        val = _text(is_) if is_ is not None else ""
                    else:
                        v = c.find("m:v", _NS)
                        val = v.text if v is not None and v.text else ""
                    cells[idx] = val
                if cells:
                    width = max(cells) + 1
                    rows.append([cells.get(i, "") for i in range(width)])
                else:
                    rows.append([])
            out[name] = rows
        return out
