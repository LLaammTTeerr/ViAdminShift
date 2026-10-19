"""RAG contexts for every item: ``data/benchmark/contexts.jsonl`` + generated passages
``data/benchmark/template_passages.jsonl``.

Passage kinds (field ``source``):
* ``wiki_excerpt`` -- a short excerpt of a real Wikipedia passage from data/wiki/passages.jsonl
  (``derived_from`` = its passage_id; title / revision_id / revision_timestamp copied). We never
  reference the raw wiki rows directly: their ``admin_text`` is up to 8,000 chars, so excerpts
  keep every context short whatever ``--passage-fields`` the runner uses. id prefix ``wikix_``.
* ``template`` -- encyclopedic Vietnamese text generated from the canonical tables (id prefix
  ``tpl_``), used when no wiki passage states the needed fact (checked by string match).
  Fixed timestamps: era old 2025-06-01, era new 2025-10-01 (needed by +date/+recency).

Per item and condition: none -> [], new -> [one new-era passage that contains the gold],
mixed -> [one old-era passage (contains the old answer when it changed), the SAME new passage],
order shuffled with the item's cue group RNG. Each context row also records ``must_contain``
(names verified in the passages) and the source of each passage.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from viadmin.gen.common import WIKI, Tables, key, load_jsonl, lower_prefix, rng_for, short_of
from viadmin.wiki.report import name_in_text

TS_OLD = "2025-06-01T00:00:00Z"
TS_NEW = "2025-10-01T00:00:00Z"
MAX_PASSAGE = 1250
REFORM_RE = re.compile(r"(sáp nhập|hợp nhất|giải thể).*2025|2025.*(sáp nhập|hợp nhất|giải thể)", re.I)


def has_name(name: str, text: str) -> bool:
    """Word-bounded, tone-placement/case-insensitive containment of a bare name."""
    return re.search(r"(?<!\w)" + re.escape(key(name)) + r"(?!\w)", key(text)) is not None


def _sentences(text: str) -> list[str]:
    out: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        buf = ""
        i = 0
        while i < len(line):
            buf += line[i]
            if line[i] in ".!?" and i + 2 < len(line) and line[i + 1] == " " and line[i + 2].isupper() \
                    and not re.search(r"(?:\b[A-ZĐ]|TP|Tp|St|Th)\.$", buf):
                out.append(buf.strip())
                buf = ""
                i += 1
            i += 1
        if buf.strip():
            out.append(buf.strip())
    return out


def _cap(text: str, limit: int = MAX_PASSAGE) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    j = max(cut.rfind(". "), cut.rfind("\n"))
    return (cut[: j + 1] if j > limit // 2 else cut.rsplit(" ", 1)[0] + " …").strip()


def _window(line: str, name: str, width: int = 650) -> str:
    """Cut a long list line to its head + a window around ``name``."""
    if len(line) <= width:
        return line
    m = re.search(re.escape(name), line)
    pos = m.start() if m else 0
    head = line[:220].rsplit(",", 1)[0]
    lo = max(len(head), pos - 200)
    lo = line.rfind(",", 0, lo) + 1 if line.rfind(",", 0, lo) > len(head) else lo
    hi = line.find(",", pos + 200)
    hi = len(line) if hi < 0 else hi
    return f"{head}, … {line[lo:hi].strip()}{' …' if hi < len(line) else ''}"


class Builder:
    def __init__(self, t: Tables):
        self.t = t
        self.wiki = {}
        for p in load_jsonl(WIKI / "passages.jsonl"):
            self.wiki[(p["entity_set"], p["entity_code"], p["era"])] = p
        self.quality = {q["passage_id"]: q for q in load_jsonl(WIKI / "quality.jsonl")}
        self.passages: dict[str, dict] = {}
        self.cache: dict[tuple, tuple[str, str] | None] = {}
        self.extra_area = {}
        for w in t.wards_new:
            if w["name"] == "Xã Kim Đông" and w["province_code"] == "37":
                self.extra_area[w["code"]] = "khu vực bãi bồi ven biển do huyện Kim Sơn quản lý"
            if w["name"] == "Xã Biên Sơn" and w["province_code"] == "24":
                self.extra_area[w["code"]] = "Trường bắn TB1"

    # ------------------------------------------------------------------ registration
    def _add_excerpt(self, src: dict, text: str) -> str:
        text = _cap(text)
        h = hashlib.sha1(text.encode()).hexdigest()[:8]
        pid = f"wikix_{src['passage_id']}_{h}"
        if pid not in self.passages:
            self.passages[pid] = {
                "passage_id": pid, "title": src["title"], "entity_type": src["entity_type"],
                "entity_set": src["entity_set"], "entity_code": src["entity_code"], "era": src["era"],
                "revision_id": src["revision_id"], "revision_timestamp": src["revision_timestamp"],
                "page_id": src.get("page_id"), "text": text, "admin_text": None, "infobox_text": None,
                "source": "wiki_excerpt", "derived_from": src["passage_id"],
            }
        return pid

    def _add_template(self, pid: str, title: str, era: str, text: str, entity_type: str,
                      entity_set: str | None, entity_code: str | None) -> str:
        pid = "tpl_" + pid
        p = {
            "passage_id": pid, "title": title, "entity_type": entity_type, "entity_set": entity_set,
            "entity_code": entity_code, "era": era, "revision_id": None,
            "revision_timestamp": TS_OLD if era == "old" else TS_NEW, "page_id": None,
            "text": _cap(text), "admin_text": None, "infobox_text": None, "source": "template",
        }
        assert self.passages.get(pid, p) == p, pid
        self.passages[pid] = p
        return pid

    def text(self, pid: str) -> str:
        return self.passages[pid]["text"]

    def _memo(self, k: tuple, fn):
        if k not in self.cache:
            self.cache[k] = fn()
        return self.cache[k]

    # ------------------------------------------------------------------ template texts
    def _prov_phrase(self, codes: list[str]) -> str:
        names = [lower_prefix(self.t.pold[c]["name"]) for c in codes]
        return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " và " + names[-1]

    def tpl_old_province(self, pc: str) -> str:
        p = self.t.pold[pc]
        nd = len(self.t.districts_by_prov[pc])
        nw = sum(1 for w in self.t.wards_old if w["province_code"] == pc)
        kind = "thành phố trực thuộc trung ương" if p["type"] == "thành phố" else "tỉnh"
        txt = (f"{p['name']} là một {kind} của Việt Nam. {p['name']} có {nd} đơn vị hành chính cấp huyện "
               f"và {nw} đơn vị hành chính cấp xã.")
        return self._add_template(f"oldprov_{pc}", p["short_name"], "old", txt, "province", "old_province", pc)

    def tpl_province_new(self, pc: str) -> str:
        """New-era status of OLD province pc (merged into G or kept)."""
        t = self.t
        p = t.pold[pc]
        g = t.pnew[t.new_of_old_prov[pc]]
        comps = sorted(g["merged_from"], key=lambda c: (key(t.pold[c]["short_name"]) != key(g["short_name"]), c))
        nq = "Nghị quyết số 202/2025/QH15 ngày 12 tháng 6 năm 2025 của Quốc hội về việc sắp xếp đơn vị hành chính cấp tỉnh"
        if len(comps) == 1:
            txt = (f"{p['name']} là một đơn vị hành chính cấp tỉnh của Việt Nam. {p['name']} là một trong 11 tỉnh, "
                   f"thành phố không thực hiện sắp xếp theo {nq}; từ ngày 1 tháng 7 năm 2025, {lower_prefix(p['name'])} "
                   f"giữ nguyên tên gọi và địa giới, chính quyền địa phương được tổ chức theo hai cấp (cấp tỉnh và cấp xã).")
        elif key(p["short_name"]) == key(g["short_name"]):
            txt = (f"{g['name']} là một đơn vị hành chính cấp tỉnh của Việt Nam. Theo {nq}, toàn bộ diện tích tự nhiên, "
                   f"quy mô dân số của {self._prov_phrase(comps)} được sắp xếp thành {g['type']} mới có tên gọi là "
                   f"{lower_prefix(g['name'])}; chính quyền địa phương của {lower_prefix(g['name'])} mới hoạt động từ ngày "
                   f"1 tháng 7 năm 2025.")
        else:
            txt = (f"{p['name']} là một đơn vị hành chính cấp tỉnh cũ của Việt Nam. Theo {nq}, toàn bộ diện tích tự nhiên, "
                   f"quy mô dân số của {self._prov_phrase(comps)} được sắp xếp thành {g['type']} mới có tên gọi là "
                   f"{lower_prefix(g['name'])}. Từ ngày 1 tháng 7 năm 2025, {lower_prefix(p['name'])} không còn là một "
                   f"đơn vị hành chính; địa bàn {lower_prefix(p['name'])} trước đây nay thuộc {lower_prefix(g['name'])}.")
        return self._add_template(f"provnew_{pc}", p["short_name"], "new", txt, "province", "old_province", pc)

    def tpl_new_province_comp(self, gc: str) -> str:
        t = self.t
        g = t.pnew[gc]
        comps = sorted(g["merged_from"], key=lambda c: (key(t.pold[c]["short_name"]) != key(g["short_name"]), c))
        types = defaultdict(int)
        for w in t.wards_new:
            if w["province_code"] == gc:
                types[w["type"]] += 1
        parts = [f"{types[k]} {k}" for k in ("phường", "xã", "đặc khu") if types[k]]
        cnt = f"{g['name']} có {sum(types.values())} đơn vị hành chính cấp xã, gồm " + \
            (", ".join(parts[:-1]) + " và " + parts[-1] if len(parts) > 1 else parts[0]) + "."
        if len(comps) == 1:
            txt = self.passages[self.tpl_province_new(comps[0])]["text"] + " " + cnt
            return self._add_template(f"newprov_{gc}", g["short_name"], "new", txt, "province", "new_province", gc)
        txt = (f"{g['name']} là một đơn vị hành chính cấp tỉnh của Việt Nam, được hình thành từ ngày 1 tháng 7 năm 2025. "
               f"Theo Nghị quyết số 202/2025/QH15 ngày 12 tháng 6 năm 2025 của Quốc hội, toàn bộ diện tích tự nhiên, quy mô "
               f"dân số của {self._prov_phrase(comps)} được sắp xếp thành {lower_prefix(g['name'])}. {cnt}")
        return self._add_template(f"newprov_{gc}", g["short_name"], "new", txt, "province", "new_province", gc)

    def tpl_old_ward(self, oc: str) -> str:
        t = self.t
        w = t.wold[oc]
        d = t.dold[w["district_code"]]
        p = t.pold[w["province_code"]]
        n = len(t.wards_old_by_district[d["code"]])
        txt = (f"{w['name']} là một {w['type']} thuộc {lower_prefix(d['name'])}, {lower_prefix(p['name'])}, Việt Nam. "
               f"{d['name'][:1].upper() + lower_prefix(d['name'])[1:]} có {n} đơn vị hành chính cấp xã.")
        return self._add_template(f"oldward_{oc}", f"{w['name']} ({d['short_name']}, {p['short_name']})", "old", txt,
                                  "ward", "old_ward", oc)

    def tpl_new_ward(self, nc: str) -> str:
        t = self.t
        w = t.wnew[nc]
        g = t.pnew[w["province_code"]]
        rows = sorted(t.rows_by_new.get(nc, []), key=lambda r: (r["old_province_code"], r["old_district_code"], r["old_ward_code"]))
        def grp(rs):
            by: dict[tuple, list[str]] = defaultdict(list)
            order = []
            for r in rs:
                k = (r["old_district_name"], r["old_province_name"])
                if k not in by:
                    order.append(k)
                by[k].append(lower_prefix(r["old_ward_name"]))
            segs = []
            for k in order:
                ws = by[k]
                lst = ws[0] if len(ws) == 1 else ", ".join(ws[:-1]) + " và " + ws[-1]
                segs.append(f"{lst} (thuộc {lower_prefix(k[0])}, {lower_prefix(k[1])})")
            return "; ".join(segs)
        full = [r for r in rows if not r["is_partial"]]
        part = [r for r in rows if r["is_partial"]]
        comp = []
        if full:
            comp.append(f"toàn bộ diện tích tự nhiên, quy mô dân số của {grp(full)}")
        if part:
            comp.append(f"một phần diện tích tự nhiên, quy mô dân số của {grp(part)}")
        if nc in self.extra_area:
            comp.append(f"{self.extra_area[nc]}")
        res = w.get("resolution")
        src = f"Nghị quyết số {res} ngày 16 tháng 6 năm 2025 của Ủy ban Thường vụ Quốc hội" if res else \
            "nghị quyết của Ủy ban Thường vụ Quốc hội năm 2025"
        typ = w["type"]
        if len(rows) == 1 and rows[0]["change_type"] == "unchanged":
            txt = (f"{w['name']} là một {typ} thuộc {lower_prefix(g['name'])}, Việt Nam. Theo {src}, "
                   f"{lower_prefix(w['name'])} (trước đây thuộc {lower_prefix(rows[0]['old_district_name'])}, "
                   f"{lower_prefix(rows[0]['old_province_name'])}) được giữ nguyên tên gọi và địa giới; từ ngày 1 tháng 7 "
                   f"năm 2025, {lower_prefix(w['name'])} trực thuộc {lower_prefix(g['name'])}.")
        else:
            txt = (f"{w['name']} là một {typ} thuộc {lower_prefix(g['name'])}, Việt Nam. Theo {src}, "
                   f"{lower_prefix(w['name'])} được thành lập trên cơ sở sắp xếp " + "; và ".join(comp) +
                   f". {w['name']} chính thức hoạt động từ ngày 1 tháng 7 năm 2025.")
        return self._add_template(f"newward_{nc}", f"{w['name']} ({g['short_name']})", "new", txt, "ward", "new_ward", nc)

    def tpl_district_new(self, dc: str) -> str:
        t = self.t
        d = t.dold[dc]
        p = t.pold[d["province_code"]]
        g = t.pnew[t.new_of_old_prov[p["code"]]]
        txt = (f"{d['name']} là một đơn vị hành chính cấp huyện cũ thuộc {lower_prefix(p['name'])}, Việt Nam. Từ ngày 1 tháng 7 "
               f"năm 2025, theo Nghị quyết số 203/2025/QH15 của Quốc hội sửa đổi, bổ sung một số điều của Hiến pháp, chính "
               f"quyền địa phương được tổ chức theo hai cấp (cấp tỉnh và cấp xã), cấp huyện không còn tồn tại; "
               f"{lower_prefix(d['name'])} chấm dứt hoạt động. Địa bàn {lower_prefix(d['name'])} trước đây nay thuộc "
               f"{lower_prefix(g['name'])}.")
        return self._add_template(f"distnew_{dc}", f"{d['name']} ({p['short_name']})", "new", txt, "district", "old_district", dc)

    def tpl_district_old(self, dc: str) -> str:
        t = self.t
        d = t.dold[dc]
        p = t.pold[d["province_code"]]
        n = len(t.wards_old_by_district[dc])
        txt = f"{d['name']} là một {d['type']} thuộc {lower_prefix(p['name'])}, Việt Nam. {d['name']} có {n} đơn vị hành chính cấp xã."
        return self._add_template(f"distold_{dc}", f"{d['name']} ({p['short_name']})", "old", txt, "district", "old_district", dc)

    def tpl_national(self, era: str) -> str:
        if era == "new":
            txt = ("Từ ngày 1 tháng 7 năm 2025, chính quyền địa phương ở Việt Nam được tổ chức theo mô hình hai cấp, gồm cấp "
                   "tỉnh và cấp xã; cấp huyện không còn tồn tại (Nghị quyết số 203/2025/QH15 sửa đổi, bổ sung một số điều "
                   "của Hiến pháp). Theo Nghị quyết số 202/2025/QH15 ngày 12 tháng 6 năm 2025 của Quốc hội, cả nước có 34 "
                   "đơn vị hành chính cấp tỉnh, gồm 28 tỉnh và 6 thành phố trực thuộc trung ương. Sau khi sắp xếp, cả nước "
                   "có 3.321 đơn vị hành chính cấp xã, gồm 2.621 xã, 687 phường và 13 đặc khu; thị trấn không còn là một "
                   "loại đơn vị hành chính.")
        else:
            txt = ("Việt Nam có 63 đơn vị hành chính cấp tỉnh, gồm 57 tỉnh và 6 thành phố trực thuộc trung ương. Chính "
                   "quyền địa phương được tổ chức theo ba cấp: cấp tỉnh, cấp huyện và cấp xã. Cả nước có 696 đơn vị hành "
                   "chính cấp huyện (quận, huyện, thị xã, thành phố thuộc tỉnh, thành phố thuộc thành phố trực thuộc trung "
                   "ương) và 10.035 đơn vị hành chính cấp xã, gồm xã, phường và thị trấn.")
        return self._add_template(f"national_{era}", "Đơn vị hành chính Việt Nam", era, txt, "country", None, None)

    # ------------------------------------------------------------------ wiki excerpts
    def _lead_with(self, p: dict, pred) -> str | None:
        """First sentence of the lead + the first sentence satisfying pred (None if none)."""
        sents = _sentences(p["text"] or "")
        if not sents:
            return None
        hit = next((s for s in sents if pred(s)), None)
        if hit is None:
            return None
        return sents[0] if hit == sents[0] else sents[0] + " " + hit

    def wiki_old_province(self, pc: str) -> str | None:
        def f():
            p = self.wiki.get(("old_province", pc, "old"))
            if not p:
                return None
            name = self.t.pold[pc]["short_name"]
            sents = _sentences(p["text"])
            if not sents or not has_name(name, sents[0]):
                return None
            txt = " ".join(sents[:2]) if len(" ".join(sents[:2])) <= 600 else sents[0]
            return self._add_excerpt(p, txt)
        return self._memo(("wop", pc), f)

    def wiki_new_province_old(self, gc: str) -> str | None:
        """Old-era page of the new province's namesake (describes the pre-reform province)."""
        def f():
            p = self.wiki.get(("new_province", gc, "old"))
            if not p:
                return None
            sents = _sentences(p["text"])
            if not sents or not has_name(self.t.pnew[gc]["short_name"], sents[0]):
                return None
            txt = " ".join(sents[:2]) if len(" ".join(sents[:2])) <= 600 else sents[0]
            return self._add_excerpt(p, txt)
        return self._memo(("wnpo", gc), f)

    def wiki_province_new(self, pc: str) -> str | None:
        """New-era lead of OLD province pc stating where it went (needs gold name + reform marker)."""
        def f():
            p = self.wiki.get(("old_province", pc, "new"))
            if not p or not self.quality.get(p["passage_id"], {}).get("new_text_reflects_reform"):
                return None
            g = self.t.pnew[self.t.new_of_old_prov[pc]]
            if key(g["short_name"]) == key(self.t.pold[pc]["short_name"]):
                return None  # kept/namesake: the lead does not state the (non-)merger; use a template
            gname = g["short_name"]
            pred = lambda s: has_name(gname, s) and REFORM_RE.search(s)  # noqa: E731
            txt = self._lead_with(p, pred)
            return self._add_excerpt(p, txt) if txt else None
        return self._memo(("wpn", pc), f)

    def wiki_new_province_comp(self, gc: str) -> str | None:
        def f():
            p = self.wiki.get(("new_province", gc, "new"))
            g = self.t.pnew[gc]
            if not p or len(g["merged_from"]) == 1:
                return None
            names = [self.t.pold[c]["short_name"] for c in g["merged_from"]]
            pred = lambda s: all(has_name(n, s) for n in names) and REFORM_RE.search(s)  # noqa: E731
            txt = self._lead_with(p, pred)
            return self._add_excerpt(p, txt) if txt else None
        return self._memo(("wnpc", gc), f)

    def wiki_district_old(self, dc: str, ward_short: str | None) -> str | None:
        """Old-era district page: lead sentence (names the province) + the admin line listing
        the ward. Only clean pages (count matches gold, no stale names in the list)."""
        def f():
            p = self.wiki.get(("old_district", dc, "old"))
            if not p:
                return None
            q = self.quality.get(p["passage_id"], {})
            if q.get("stated_count_matches_gold") is False or q.get("admin_names_not_in_gold") or q.get("mentions_reform"):
                return None
            d = self.t.dold[dc]
            pname = self.t.pold[d["province_code"]]["short_name"]
            sents = _sentences(p["text"])
            if not sents or not has_name(d["short_name"], sents[0]):
                return None
            lead = sents[0] if has_name(pname, sents[0]) else None
            if lead is None:
                return None
            if ward_short is None:
                return self._add_excerpt(p, lead)
            if re.fullmatch(r"\d+|[IVX]+", ward_short):
                return None  # numbered wards: list matching is unreliable -> template
            lines = [ln for ln in (p["admin_text"] or "").split("\n") if ln.strip()]
            hit = None
            for ln in lines:
                if name_in_text(ward_short, ln) and (" | " in ln or re.search(r"đơn vị hành chính|bao gồm|\bgồm\b", ln)):
                    hit = ln
                    break
            if hit is None:
                return None
            if " | " in hit:
                body = lines[0] + "\n" + hit if lines[0] != hit else hit
            else:
                body = _window(hit, ward_short)
            if not name_in_text(ward_short, body):
                return None
            return self._add_excerpt(p, lead + "\n" + body)
        return self._memo(("wdo", dc, ward_short), f)

    def wiki_district_new(self, dc: str) -> str | None:
        def f():
            p = self.wiki.get(("old_district", dc, "new"))
            if not p or not self.quality.get(p["passage_id"], {}).get("new_text_reflects_reform"):
                return None
            d = self.t.dold[dc]
            sents = _sentences(p["text"])
            if not sents:
                return None
            s0 = sents[0]
            # must say the district is a former one ("là một huyện cũ", "trước đây là") and name its province
            if not (has_name(d["short_name"], s0) and re.search(r"\bcũ\b|trước đây", s0)
                    and has_name(self.t.pold[d["province_code"]]["short_name"], s0)):
                return None
            return self._add_excerpt(p, s0)
        return self._memo(("wdn", dc), f)

    def wiki_new_ward_listing(self, nc: str) -> str | None:
        """New-province admin table: summary line + table title + section header + the ward's row."""
        def f():
            w = self.t.wnew[nc]
            g = self.t.pnew[w["province_code"]]
            p = self.wiki.get(("new_province", g["code"], "new"))
            if not p or not p.get("admin_text"):
                return None
            lines = [ln for ln in p["admin_text"].split("\n") if ln.strip()]
            row_i = None
            for i, ln in enumerate(lines):
                cell0 = ln.split(" | ")[0].strip()
                if " | " in ln and key(cell0) == key(w["short_name"]):
                    row_i = i
                    break
            if row_i is None:
                return None
            sec = next((lines[j] for j in range(row_i - 1, -1, -1)
                        if re.match(r"^(Phường|Xã|Đặc khu)\s*\(\d+\)$", lines[j].strip())), None)
            if sec is None or not sec.lower().startswith(w["type"]):
                return None  # the section's unit type must agree with wards_new
            title = next((ln for ln in lines[:row_i] if ln.startswith("Danh sách")), None)
            header = next((ln for ln in lines[:row_i] if " | " in ln and ln.startswith("Tên")), None)
            summary = lines[0]
            if not has_name(g["short_name"], summary):
                return None
            body = "\n".join(x for x in (summary, title, header, sec, lines[row_i]) if x)
            return self._add_excerpt(p, body)
        return self._memo(("wnl", nc), f)


# ----------------------------------------------------------------------------- per item

def wn(full: str) -> str:
    """Name to verify in a passage: the bare name, or the prefixed one for numbered wards
    ("Phường 4", "Phường IV") whose bare form would match any number in the text."""
    short = short_of(full)
    return full if re.fullmatch(r"\d+|[IVXLC]+", short) else short


def _pick(wiki_pid: str | None, tpl) -> tuple[str, str]:
    if wiki_pid:
        return wiki_pid, "wiki"
    return tpl(), "template"


def plan_item(b: Builder, it: dict) -> dict:
    """Return {new: (pid, src), old: (pid, src), must_new: [...], must_old: [...]}."""
    t = b.t
    m = it["meta"]
    q = it["qtype"]
    if q == "T0_headline":
        return dict(new=(b.tpl_national("new"), "template"), old=(b.tpl_national("old"), "template"),
                    must_new=[], must_old=[])
    if q in ("T6_reverse",) or (q == "T3_existence" and m["entity_kind"] == "province"):
        pc = m["old_province_code"]
        g = t.pnew[m["new_province_code"]]
        new = _pick(b.wiki_province_new(pc), lambda: b.tpl_province_new(pc))
        old = _pick(b.wiki_old_province(pc), lambda: b.tpl_old_province(pc))
        return dict(new=new, old=old, must_new=[g["short_name"], t.pold[pc]["short_name"]],
                    must_old=[t.pold[pc]["short_name"]])
    if q == "T2_composition":
        gc = m["new_province_code"]
        new = _pick(b.wiki_new_province_comp(gc), lambda: b.tpl_new_province_comp(gc))
        old = _pick(b.wiki_new_province_old(gc), lambda: b.tpl_old_province(
            next(c for c in t.pnew[gc]["merged_from"] if key(t.pold[c]["short_name"]) == key(t.pnew[gc]["short_name"]))))
        return dict(new=new, old=old, must_new=[t.pold[c]["short_name"] for c in m["components"]],
                    must_old=[t.pnew[gc]["short_name"]])
    if q in ("T1_membership", "T5_ward_successor", "T4_address") or \
            (q == "T3_existence" and m["entity_kind"] in ("abolished_ward", "unchanged_ward")):
        oc = m["old_ward_code"]
        w = t.wold[oc]
        rows = t.rows_by_old[oc]
        pc = rows[0]["old_province_code"]
        g = t.pnew[rows[0]["new_province_code"]]
        old = _pick(b.wiki_district_old(w["district_code"], w["short_name"]), lambda: b.tpl_old_ward(oc))
        must_old = [wn(w["name"]), t.pold[pc]["short_name"]]
        if q == "T1_membership":
            if len(g["merged_from"]) > 1 and key(g["short_name"]) != key(t.pold[pc]["short_name"]):
                new = _pick(b.wiki_province_new(pc), lambda: b.tpl_province_new(pc))
            else:
                new = (b.tpl_province_new(pc), "template")
            return dict(new=new, old=old, must_new=[g["short_name"]], must_old=must_old)
        if q == "T3_existence" and m["entity_kind"] == "unchanged_ward":
            nc = rows[0]["new_ward_code"]
            new = _pick(b.wiki_new_ward_listing(nc), lambda: b.tpl_new_ward(nc))
            return dict(new=new, old=old, must_new=[wn(t.wnew[nc]["name"])], must_old=must_old)
        nc = rows[0]["new_ward_code"]
        new = (b.tpl_new_ward(nc), "template")  # wiki has no old->new ward composition
        must_new = [wn(t.wnew[nc]["name"]), wn(w["name"])] + ([g["short_name"]] if q == "T4_address" else [])
        return dict(new=new, old=old, must_new=must_new, must_old=must_old)
    if q == "T1_newname" or (q == "T3_existence" and m["entity_kind"] == "new_ward"):
        nc = m["new_ward_code"]
        w = t.wnew[nc]
        g = t.pnew[w["province_code"]]
        new = _pick(b.wiki_new_ward_listing(nc), lambda: b.tpl_new_ward(nc))
        must_old: list[str] = []
        old = None
        oap = m.get("old_answer_province") if q == "T1_newname" else None
        if oap:
            k = key(w["short_name"])
            ow = [x for x in t.old_ward_keys.get(k, []) if x["province_code"] == oap]
            od = [x for x in t.old_district_keys.get(k, []) if x["province_code"] == oap]
            if ow:
                o = sorted(ow, key=lambda x: x["code"])[0]
                old = _pick(b.wiki_district_old(o["district_code"], o["short_name"]), lambda: b.tpl_old_ward(o["code"]))
            else:
                o = sorted(od, key=lambda x: x["code"])[0]
                old = _pick(b.wiki_district_old(o["code"], None), lambda: b.tpl_district_old(o["code"]))
            must_old = [wn(w["name"]), t.pold[oap]["short_name"]]
        else:
            old = _pick(b.wiki_new_province_old(g["code"]), lambda: b.tpl_old_province(
                next(c for c in g["merged_from"] if key(t.pold[c]["short_name"]) == key(g["short_name"]))))
        return dict(new=new, old=old, must_new=[wn(w["name"]), g["short_name"]], must_old=must_old)
    if q == "T3_existence" and m["entity_kind"] == "district":
        dc = m["old_district_code"]
        new = _pick(b.wiki_district_new(dc), lambda: b.tpl_district_new(dc))
        old = _pick(b.wiki_district_old(dc, None), lambda: b.tpl_district_old(dc))
        d = t.dold[dc]
        return dict(new=new, old=old, must_new=[d["short_name"]], must_old=[d["short_name"]])
    raise ValueError(f"no context plan for {it['id']}")


def build_contexts(t: Tables, items: list[dict]) -> tuple[list[dict], list[dict]]:
    b = Builder(t)
    rows: list[dict] = []
    for it in items:
        plan = plan_item(b, it)
        (npid, nsrc), (opid, osrc) = plan["new"], plan["old"]
        for nm in plan["must_new"]:
            if not has_name(nm, b.text(npid)):
                raise AssertionError(f"{it['id']}: new passage {npid} lacks {nm!r}")
        for nm in plan["must_old"]:
            if not has_name(nm, b.text(opid)):
                raise AssertionError(f"{it['id']}: old passage {opid} lacks {nm!r}")
        it["meta"]["context_source"] = nsrc
        it["meta"]["context_source_old"] = osrc
        grp = it["meta"].get("cue_group") or it["meta"].get("twin_id") or it["id"]
        mixed = [opid, npid]
        rng_for("mixed:" + grp).shuffle(mixed)
        rows.append({"item_id": it["id"], "condition": "none", "passages": []})
        rows.append({"item_id": it["id"], "condition": "new", "passages": [npid], "sources": [nsrc],
                     "must_contain": plan["must_new"]})
        rows.append({"item_id": it["id"], "condition": "mixed", "passages": mixed,
                     "sources": [nsrc if p == npid else osrc for p in mixed],
                     "eras": ["new" if p == npid else "old" for p in mixed],
                     "must_contain": plan["must_new"], "must_contain_old": plan["must_old"]})
    passages = [b.passages[k] for k in sorted(b.passages)]
    return passages, rows
