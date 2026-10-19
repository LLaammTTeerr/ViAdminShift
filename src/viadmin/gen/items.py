"""Benchmark item builders (one function per qtype). See docs/SPEC.md "Benchmark items"
and docs/benchmark_report.md for the design.

Conventions
-----------
* Gold labels come only from ``ward_mapping`` rows with ``confidence == "high"`` (all rows
  are high at the time of writing; the filter is enforced anyway).
* Every random choice uses ``rng_for(<stable key>)`` (seed 13 + key) so adding or removing an
  item never changes the others.
* Cue variants (SPEC addendum 2) share the choice order (shuffled by ``cue_group``).
* "Surface-changed" rule: in the large changed cells an old ward is eligible only when the
  surface of what is asked actually changed (province_changed => province_name_changed,
  ward_changed => name_changed). The two small control cells (pc0_wc0, pc1_wc0) are used in
  full (SPEC); their rows keep ``meta.surface_answer_changed`` so analyses can split them.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from viadmin.data.normalize import loose_key
from viadmin.eval.validate import lint_item
from viadmin.gen.common import (
    Tables,
    key,
    lc_first,
    lower_prefix,
    nodiac,
    norm_choice,
    rng_for,
    short_of,
)

LETTERS = "ABCD"
CUES = (
    ("none", ""),
    ("date", "Tính đến tháng 10/2026, "),
    ("reform", "Sau đợt sắp xếp đơn vị hành chính năm 2025, "),
)

# sample sizes (base items, before cue/format expansion)
N_T1_CHANGED = 400  # per changed cell (pc0_wc1, pc1_wc1); control cells: all rows
N_T5_CHANGED = 150
N_T4_TOTAL = 800
N_T4_NODIAC = 400
N_T1N = {"reused_old": 120, "pc1_other": 60, "pc0": 60}
N_T3 = {"district": 60, "new_ward": 60, "abolished_ward": 65, "unchanged_ward": 60}

T3_CHOICES = {
    "P": "Có, là đơn vị hành chính cấp tỉnh",
    "D": "Có, là đơn vị hành chính cấp huyện",
    "W": "Có, là đơn vị hành chính cấp xã",
    "N": "Không, hiện không còn (hoặc không phải) là một đơn vị hành chính",
}


# ----------------------------------------------------------------------------- helpers

def cell(pc: bool | None, wc: bool | None) -> str:
    if pc is None or wc is None:
        return "na"
    return f"pc{int(pc)}_wc{int(wc)}"


def mcq(base_id: str, gold: str, distractors: list[str], old: str | None) -> tuple[list[str], str, str | None]:
    """Shuffle [gold]+distractors with the base id's RNG; return (choices, gold letter, old letter)."""
    opts = [gold, *distractors]
    assert len(opts) == 4, (base_id, opts)
    keys = [norm_choice(o) for o in opts]
    assert len(set(keys)) == 4, (base_id, opts)
    rng_for("choices:" + base_id).shuffle(opts)
    gl = LETTERS[opts.index(gold)]
    ol = LETTERS[opts.index(old)] if old is not None else None
    return opts, gl, ol


def pick_distinct(cands: Iterable[str], taken: list[str], n: int) -> list[str]:
    """First n candidates whose normalised name (and diacritic-free form) is new."""
    seen = {norm_choice(x) for x in taken} | {nodiac(norm_choice(x)) for x in taken}
    out: list[str] = []
    for c in cands:
        k = norm_choice(c)
        if k in seen or nodiac(k) in seen:
            continue
        seen |= {k, nodiac(k)}
        out.append(c)
        if len(out) == n:
            break
    if len(out) < n:
        raise ValueError(f"not enough distractors: {taken} -> {out}")
    return out


def cue_variants(base_id: str, base_q: str) -> list[tuple[str, str, str]]:
    """[(item id, cue, question)] for the three cue variants."""
    return [(f"{base_id}__{cue}", cue, (pre + lc_first(base_q)) if pre else base_q) for cue, pre in CUES]


def round_robin_sample(groups: dict[str, list], n: int, tag: str) -> list:
    """Sample n elements spread evenly over groups (sorted keys), each group shuffled."""
    pools = {}
    for g in sorted(groups):
        lst = list(groups[g])
        rng_for(f"{tag}:{g}").shuffle(lst)
        pools[g] = lst
    out: list = []
    order = sorted(pools)
    rng_for(f"{tag}:order").shuffle(order)
    while len(out) < n and any(pools.values()):
        for g in order:
            if pools[g] and len(out) < n:
                out.append(pools[g].pop())
    return out


class Ctx:
    """Derived per-old-ward facts."""

    def __init__(self, t: Tables):
        self.t = t
        self.old = {}
        for code, rows in t.rows_by_old.items():
            if any(r["confidence"] != "high" for r in rows):
                continue  # gold labels only from high-confidence rows
            r = rows[0]
            pc, wc = r["province_changed"], r["ward_changed"]
            pnc = r["province_name_changed"]
            # bare-name change: a pure unit-type change (Thị trấn X -> Xã X) is NOT a surface
            # change, because the scorer strips unit prefixes before matching
            nc_all = all(bare_changed(x) for x in rows)
            divided = len(rows) > 1
            surface = (pnc if pc else True) and (nc_all if wc else True)
            self.old[code] = dict(
                rows=rows, pc=pc, wc=wc, pnc=pnc, nc_all=nc_all, divided=divided,
                cell=cell(pc, wc), surface_ok=surface,
                surface_answer_changed=any(x["surface_answer_changed"] for x in rows),
            )

    def by_cell(self, pred) -> dict[str, list[str]]:
        d: dict[str, list[str]] = defaultdict(list)
        for code in sorted(self.old):
            o = self.old[code]
            if pred(code, o):
                d[o["cell"]].append(code)
        return d


def bare_changed(r: dict) -> bool:
    return key(short_of(r["old_ward_name"])) != key(short_of(r["new_ward_name"]))


def old_addr_parts(t: Tables, r: dict) -> tuple[str, str, str]:
    return r["old_ward_name"], r["old_district_name"], r["old_province_name"]


def base_meta(r: dict, **kw) -> dict:
    m = dict(
        province_changed=r["province_changed"],
        ward_changed=r["ward_changed"],
        change_type=r["change_type"],
        old_province_code=r["old_province_code"],
        new_province_code=r["new_province_code"],
        old_ward_code=r["old_ward_code"],
        new_ward_code=r["new_ward_code"],
        consistency_group=r["old_province_code"],
        has_diacritics=True,
        name_changed=r["name_changed"],
        province_name_changed=r["province_name_changed"],
        surface_answer_changed=r["surface_answer_changed"],
        old_ward_name=r["old_ward_name"],
        old_district_name=r["old_district_name"],
        old_province_name=r["old_province_name"],
        new_ward_name=r["new_ward_name"],
        new_province_name=r["new_province_name"],
    )
    m.update(kw)
    return m


def item(iid: str, qtype: str, question: str, fmt: str, choices, answer, old, meta: dict,
         aliases: list[str] | None = None) -> dict:
    return dict(id=iid, qtype=qtype, question=question, format=fmt, choices=choices, answer=answer,
                answer_aliases=aliases or [], old_answer=old, meta=meta)


def hint_in_question(question: str, gold_short: str) -> bool:
    """The gold's bare name occurs in the question as whole words, compared without diacritics (e.g. new ward named
    after the old district; "Hòa" = "Hoà" = "Hoa")."""
    return f" {loose_key(gold_short)} " in f" {loose_key(question)} "


# ----------------------------------------------------------------------------- T0

def build_t0() -> list[list[dict]]:
    """Headline facts (verified: NQ 202/2025/QH15, NQ 203/2025/QH15, data/processed counts,
    the verified headline_probe.jsonl)."""
    m = dict(province_changed=None, ward_changed=None, change_type=None, old_province_code=None,
             new_province_code=None, old_ward_code=None, new_ward_code=None, consistency_group=None,
             has_diacritics=True, depth="surface", cue=None, cue_group=None)
    specs = [
        ("short", "Việt Nam hiện có bao nhiêu đơn vị hành chính cấp tỉnh (tỉnh và thành phố trực thuộc trung ương)?",
         "34", [], "63", None, "n_provinces"),
        ("mcq", "Hiện nay cả nước Việt Nam có bao nhiêu tỉnh, thành phố trực thuộc trung ương?",
         "34", ["63", "28", "45"], "63", None, "n_provinces"),
        ("short", "Chính quyền địa phương ở Việt Nam hiện được tổ chức theo mô hình mấy cấp?",
         "2", [], "3", None, "n_levels"),
        ("mcq", "Chính quyền địa phương ở Việt Nam hiện nay gồm những cấp nào?",
         "Cấp tỉnh và cấp xã", ["Cấp tỉnh, cấp huyện và cấp xã", "Cấp tỉnh và cấp huyện", "Cấp huyện và cấp xã"],
         "Cấp tỉnh, cấp huyện và cấp xã", None, "n_levels"),
        ("mcq", "Ở Việt Nam hiện nay, cấp huyện (quận, huyện, thị xã, thành phố thuộc tỉnh) có còn là một cấp đơn vị hành chính không?",
         "Không, cấp huyện không còn tồn tại", ["Có, vẫn tồn tại ở tất cả các tỉnh, thành phố",
                                                "Chỉ còn tồn tại ở các thành phố trực thuộc trung ương",
                                                "Chỉ còn tồn tại ở các tỉnh miền núi"],
         "Có, vẫn tồn tại ở tất cả các tỉnh, thành phố", None, "district_level_abolished"),
        ("mcq", "Hiện nay Việt Nam có bao nhiêu đơn vị hành chính cấp huyện?",
         "Không có (cấp huyện không còn tồn tại)", ["696", "705", "63"], "696", None, "district_level_abolished"),
        ("short", "Việt Nam hiện có bao nhiêu đơn vị hành chính cấp xã (gồm xã, phường và đặc khu)?",
         "3321", ["3.321", "3,321"], ["10035", "10.035", "10,035"], None, "n_communes"),
        ("mcq", "Hiện nay cả nước có bao nhiêu đơn vị hành chính cấp xã?",
         "3.321", ["10.035", "4.528", "6.714"], "10.035", None, "n_communes"),
        ("mcq", "Đơn vị hành chính cấp xã ở Việt Nam hiện nay gồm những loại nào?",
         "Xã, phường và đặc khu", ["Xã, phường và thị trấn", "Xã, phường, thị trấn và đặc khu", "Xã và phường"],
         "Xã, phường và thị trấn", None, "commune_types"),
        ("mcq", "Ở Việt Nam hiện nay, thị trấn có còn là một loại đơn vị hành chính không?",
         "Không, thị trấn không còn là một loại đơn vị hành chính",
         ["Có, là đơn vị hành chính cấp xã", "Có, là đơn vị hành chính cấp huyện", "Chỉ còn ở các tỉnh miền núi"],
         "Có, là đơn vị hành chính cấp xã", None, "commune_types"),
        ("short", "Việt Nam hiện có bao nhiêu đặc khu (đơn vị hành chính cấp xã ở hải đảo)?",
         "13", [], "0", None, "n_special_zones"),
        ("short", "Cả nước hiện có tổng cộng bao nhiêu tỉnh và thành phố trực thuộc trung ương?",
         "34", [], "63", None, "n_provinces"),
    ]
    groups = []
    for i, (fmt, q, gold, extra, old, _, fact) in enumerate(specs, 1):
        iid = f"T0-{i:02d}"
        meta = dict(m, fact=fact)
        if fmt == "mcq":
            ch, gl, ol = mcq(iid, gold, extra, old)
            groups.append([item(iid, "T0_headline", q, "mcq", ch, gl, ol, meta)])
        else:
            groups.append([item(iid, "T0_headline", q, "short", None, gold, old, meta, aliases=extra)])
    return groups


# ----------------------------------------------------------------------------- T6 / T2

def build_t6(t: Tables) -> list[list[dict]]:
    groups = []
    for p in sorted(t.provinces_old, key=lambda x: x["code"]):
        g = t.pnew[t.new_of_old_prov[p["code"]]]
        pc = len(g["merged_from"]) > 1
        changed = key(p["short_name"]) != key(g["short_name"])
        base_q = f"Địa bàn {lower_prefix(p['name'])} thuộc đơn vị hành chính cấp tỉnh nào?"
        near = [t.pnew[c]["name"] for c in t.nearest_new_provinces(t.old_prov_xy[p["code"]], {g["code"]})]
        old_choice = p["name"] if changed else None
        taken = [g["name"]] + ([old_choice] if old_choice else [])
        dis = ([old_choice] if old_choice else []) + pick_distinct(near, taken, 4 - len(taken))
        for fmt in ("mcq", "short"):
            bid = f"T6-{p['code']}-{fmt}"
            meta = dict(province_changed=pc, ward_changed=None, change_type="merged" if pc else "unchanged",
                        old_province_code=p["code"], new_province_code=g["code"], old_ward_code=None,
                        new_ward_code=None, consistency_group=p["code"], has_diacritics=True,
                        province_name_changed=changed, surface_answer_changed=changed,
                        old_province_name=p["name"], new_province_name=g["name"], depth="surface",
                        cue_group=bid)
            grp = []
            for iid, cue, q in cue_variants(bid, base_q):
                mm = dict(meta, cue=cue)
                if fmt == "mcq":
                    ch, gl, ol = mcq(bid, g["name"], dis, old_choice)
                    grp.append(item(iid, "T6_reverse", q, "mcq", ch, gl, ol, mm))
                else:
                    grp.append(item(iid, "T6_reverse", q, "short", None, g["name"], old_choice, mm))
            groups.append(grp)
    return groups


def _prov_list(t: Tables, codes: list[str], namesake: str) -> str:
    """'Tỉnh Hà Giang và tỉnh Tuyên Quang' with the namesake first, then by name."""
    order = sorted(codes, key=lambda c: (c != namesake, key(t.pold[c]["short_name"])))
    names = [t.pold[c]["name"] for c in order]
    names = [names[0]] + [lower_prefix(n) for n in names[1:]]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " và " + names[-1]


def build_t2(t: Tables) -> list[list[dict]]:
    groups = []
    for g in sorted(t.provinces_new, key=lambda x: x["code"]):
        comps = list(g["merged_from"])
        namesake = next(c for c in comps if key(t.pold[c]["short_name"]) == key(g["short_name"]))
        others = [c for c in comps if c != namesake]
        xy = t.old_prov_xy[namesake]
        near = t.nearest_old_provinces(xy, set(comps))
        only = f"Chỉ có {lower_prefix(t.pold[namesake]['name'])} (giữ nguyên, không sáp nhập với tỉnh, thành phố nào)"
        gold = only if not others else _prov_list(t, comps, namesake)
        cands: list[str] = []
        if others:
            cands.append(only)  # = the answer under the old structure
            # swap one non-namesake component for the nearest outside neighbour
            swap = sorted(others)[-1]
            cands.append(_prov_list(t, [c for c in comps if c != swap] + [near[0]], namesake))
            if len(comps) >= 3:
                cands.append(_prov_list(t, [c for c in comps if c != sorted(others)[0]], namesake))
            cands.append(_prov_list(t, comps + [near[1]], namesake))
            cands.append(_prov_list(t, [namesake, near[2]], namesake))
        else:
            cands += [_prov_list(t, [namesake, near[0]], namesake), _prov_list(t, [namesake, near[1]], namesake),
                      _prov_list(t, [namesake, near[0], near[2]], namesake)]
        dis = []
        for c in cands:
            if c != gold and c not in dis:
                dis.append(c)
        dis = dis[:3]
        bid = f"T2-{g['code']}"
        q = f"{g['name']} hiện nay được hình thành từ (những) đơn vị hành chính cấp tỉnh nào trước đây?"
        old = only if others else None
        ch, gl, ol = mcq(bid, gold, dis, old)
        meta = dict(province_changed=bool(others), ward_changed=None, change_type="merged" if others else "unchanged",
                    old_province_code=None, new_province_code=g["code"], old_ward_code=None, new_ward_code=None,
                    consistency_group=None, has_diacritics=True, depth="surface", cue=None, cue_group=None,
                    components=sorted(comps), new_province_name=g["name"])
        groups.append([item(bid, "T2_composition", q, "mcq", ch, gl, ol, meta)])
    return groups


# ----------------------------------------------------------------------------- T1 compose

def build_t1(t: Tables, c: Ctx) -> list[list[dict]]:
    cells = c.by_cell(lambda code, o: True)
    chosen: list[str] = []
    for cl in ("pc0_wc0", "pc1_wc0"):
        chosen += cells[cl]  # control cells: all rows
    for cl in ("pc0_wc1", "pc1_wc1"):
        by_prov: dict[str, list[str]] = defaultdict(list)
        for code in cells[cl]:
            if c.old[code]["surface_ok"]:
                by_prov[c.old[code]["rows"][0]["old_province_code"]].append(code)
        chosen += round_robin_sample(by_prov, N_T1_CHANGED, f"T1:{cl}")
    groups = []
    for code in sorted(chosen):
        o = c.old[code]
        r = o["rows"][0]
        g = t.pnew[r["new_province_code"]]
        w, d, p = old_addr_parts(t, r)
        base_q = f"{w}, {lower_prefix(d)}, {lower_prefix(p)} thuộc tỉnh/thành phố nào?"
        changed = key(short_of(p)) != key(g["short_name"])
        old_choice = p if changed else None
        near = [t.pnew[x]["name"] for x in t.nearest_new_provinces(t.xy_old_ward(code), {g["code"]})]
        taken = [g["name"]] + ([old_choice] if old_choice else [])
        dis = ([old_choice] if old_choice else []) + pick_distinct(near, taken, 4 - len(taken))
        bid = f"T1-{code}"
        meta = base_meta(r, depth="compose", cue_group=bid, divided=o["divided"],
                         new_ward_code=None if o["divided"] else r["new_ward_code"],
                         new_ward_name=None if o["divided"] else r["new_ward_name"],
                         new_ward_codes=sorted({x["new_ward_code"] for x in o["rows"]}),
                         name_changed=o["nc_all"], change_type=r["change_type"],
                         surface_answer_changed=changed, cell_pure=o["surface_ok"])
        ch, gl, ol = mcq(bid, g["name"], dis, old_choice)
        grp = []
        for iid, cue, q in cue_variants(bid, base_q):
            grp.append(item(iid, "T1_membership", q, "mcq", ch, gl, ol, dict(meta, cue=cue)))
        groups.append(grp)
    return groups


# ----------------------------------------------------------------------------- T5 successor

def _t5_ok(t: Tables, code: str, o: dict) -> bool:
    if o["divided"]:
        return False
    r = o["rows"][0]
    if o["wc"] and bare_changed(r):
        # the old name must not be the name of another current ward of the same new province
        hits = t.new_ward_keys_by_prov[r["new_province_code"]].get(key(short_of(r["old_ward_name"])), [])
        if any(h != r["new_ward_code"] for h in hits):
            return False
    return True


def build_t5(t: Tables, c: Ctx) -> list[list[dict]]:
    cells = c.by_cell(lambda code, o: _t5_ok(t, code, o))
    chosen: list[str] = list(cells["pc0_wc0"]) + list(cells["pc1_wc0"])
    for cl in ("pc0_wc1", "pc1_wc1"):
        by_prov: dict[str, list[str]] = defaultdict(list)
        for code in cells[cl]:
            if c.old[code]["surface_ok"]:
                by_prov[c.old[code]["rows"][0]["old_province_code"]].append(code)
        chosen += round_robin_sample(by_prov, N_T5_CHANGED, f"T5:{cl}")
    groups = []
    for code in sorted(chosen):
        o = c.old[code]
        r = o["rows"][0]
        w, d, p = old_addr_parts(t, r)
        gold = r["new_ward_name"]
        base_q = f"Địa bàn {lower_prefix(w)}, {lower_prefix(d)}, {lower_prefix(p)} thuộc đơn vị hành chính cấp xã nào?"
        changed = bare_changed(r)
        old_choice = w if changed else None
        near = [t.wnew[x]["name"] for x in t.nearest_new_wards(r["new_ward_code"])]
        taken = [gold] + ([old_choice] if old_choice else [])
        dis = ([old_choice] if old_choice else []) + pick_distinct(near, taken, 4 - len(taken))
        old_short = None
        if changed:
            old_short = [w] + ([r["old_ward_name_alt"]] if r.get("old_ward_name_alt") else [])
            old_short = old_short if len(old_short) > 1 else w
        for fmt in ("mcq", "short"):
            bid = f"T5-{code}-{fmt}"
            meta = base_meta(r, depth="deep", cue_group=bid, cell_pure=o["surface_ok"], surface_answer_changed=changed,
                             gold_name_in_question=hint_in_question(base_q, short_of(gold)))
            grp = []
            for iid, cue, q in cue_variants(bid, base_q):
                mm = dict(meta, cue=cue)
                if fmt == "mcq":
                    ch, gl, ol = mcq(bid, gold, dis, old_choice)
                    grp.append(item(iid, "T5_ward_successor", q, "mcq", ch, gl, ol, mm))
                else:
                    grp.append(item(iid, "T5_ward_successor", q, "short", None, gold, old_short, mm))
            groups.append(grp)
    return groups


# ----------------------------------------------------------------------------- T1 newname

def newname_namesakes(t: Tables, w: dict) -> set[str]:
    """Old provinces holding an old ward or old district with the same bare name."""
    k = key(w["short_name"])
    s = {x["province_code"] for x in t.old_ward_keys.get(k, [])}
    s |= {x["province_code"] for x in t.old_district_keys.get(k, [])}
    return s


def build_t1n(t: Tables) -> list[list[dict]]:
    cats: dict[str, dict[str, list[str]]] = {k: defaultdict(list) for k in N_T1N}
    info = {}
    for w in sorted(t.wards_new, key=lambda x: x["code"]):
        if t.new_ward_key_count[key(w["short_name"])] != 1:
            continue  # unique bare name nationwide among new wards
        rows = t.rows_by_new.get(w["code"], [])
        if not rows or any(r["confidence"] != "high" for r in rows):
            continue  # island đặc khu without mapping rows are skipped
        g = t.pnew[w["province_code"]]
        s = newname_namesakes(t, w)
        if s and (len(s) > 1 or not s <= set(g["merged_from"])):
            continue  # old namesakes in several/other provinces: outdated answer not unique
        old_prov = next(iter(s)) if s else None
        old_ans = None
        if old_prov and key(t.pold[old_prov]["short_name"]) != key(g["short_name"]):
            old_ans = old_prov
        pc = len(g["merged_from"]) > 1
        wc = any(r["change_type"] != "unchanged" for r in rows)
        info[w["code"]] = (w, g, s, old_prov, old_ans, pc, wc, rows)
        cat = "reused_old" if old_ans else ("pc1_other" if pc else "pc0")
        cats[cat][g["code"]].append(w["code"])
    chosen = []
    for cat, n in N_T1N.items():
        chosen += round_robin_sample(cats[cat], n, f"T1N:{cat}")
    groups = []
    for code in sorted(chosen):
        w, g, s, old_prov, old_ans, pc, wc, rows = info[code]
        base_q = f"{w['name']} thuộc tỉnh/thành phố nào?"
        old_choice = t.pold[old_ans]["name"] if old_ans else None
        near = [t.pnew[x]["name"] for x in t.nearest_new_provinces(t.xy_new_ward(code), {g["code"]})]
        taken = [g["name"]] + ([old_choice] if old_choice else [])
        dis = ([old_choice] if old_choice else []) + pick_distinct(near, taken, 4 - len(taken))
        bid = f"T1N-{code}"
        meta = dict(province_changed=pc, ward_changed=wc,
                    change_type=("unchanged" if not wc else ("renamed" if len(rows) == 1 and rows[0]["change_type"] == "renamed" else "merged")),
                    old_province_code=old_prov, new_province_code=g["code"], old_ward_code=None,
                    new_ward_code=code, consistency_group=None, has_diacritics=True, depth="deep",
                    cue_group=bid, name_reused_from_old=bool(s), old_answer_province=old_ans,
                    new_ward_name=w["name"], new_province_name=g["name"],
                    old_province_name=t.pold[old_prov]["name"] if old_prov else None,
                    surface_answer_changed=bool(old_ans),
                    old_ward_codes=sorted({r["old_ward_code"] for r in rows}))
        ch, gl, ol = mcq(bid, g["name"], dis, old_choice)
        grp = [item(iid, "T1_newname", q, "mcq", ch, gl, ol, dict(meta, cue=cue))
               for iid, cue, q in cue_variants(bid, base_q)]
        groups.append(grp)
    return groups


# ----------------------------------------------------------------------------- T4 address

def _house(code: str, ward_type: str, prov_code: str) -> str:
    rng = rng_for("house:" + code)
    n = rng.randint(2, 189)
    m = rng.randint(1, 12)
    south = int(prov_code) >= 70
    if ward_type in ("phường", "thị trấn"):
        unit = "khu phố" if south else "tổ dân phố"
    else:
        unit = "ấp" if south else "thôn"
    return f"Số {n}, {unit} {m}"


def build_t4(t: Tables, c: Ctx) -> list[list[dict]]:
    ok = lambda code, o: not o["divided"]  # noqa: E731  divided wards have no unique new ward
    cells = c.by_cell(ok)
    chosen = list(cells["pc0_wc0"]) + list(cells["pc1_wc0"])
    rest = N_T4_TOTAL - len(chosen)
    for i, cl in enumerate(("pc0_wc1", "pc1_wc1")):
        n = rest // 2 + (rest % 2 if i == 0 else 0)
        by_prov: dict[str, list[str]] = defaultdict(list)
        for code in cells[cl]:
            if c.old[code]["surface_ok"]:
                by_prov[c.old[code]["rows"][0]["old_province_code"]].append(code)
        chosen += round_robin_sample(by_prov, n, f"T4:{cl}")
    items_by_code = {}
    for code in sorted(chosen):
        o = c.old[code]
        r = o["rows"][0]
        w, d, p = old_addr_parts(t, r)
        house = _house(code, r["old_ward_type"], r["old_province_code"])
        addr = f"{house}, {lower_prefix(w)}, {lower_prefix(d)}, {lower_prefix(p)}"
        gold = f"{r['new_ward_name']}, {r['new_province_name']}"
        surface = bare_changed(r) or r["province_name_changed"]
        old = f"{w}, {d}, {p}" if surface else None
        q = f"Địa chỉ cũ: {addr}. Địa chỉ này hiện nay được viết theo đơn vị hành chính hai cấp (cấp xã, cấp tỉnh) như thế nào?"
        meta = base_meta(r, depth="deep", surface_answer_changed=surface, gold_ward=r["new_ward_name"], gold_province=r["new_province_name"],
                         old_address=old or f"{w}, {d}, {p}", house_part=house, cue=None, cue_group=None,
                         cell_pure=o["surface_ok"], twin_id=None,
                         gold_name_in_question=hint_in_question(q, short_of(r["new_ward_name"])))
        items_by_code[code] = item(f"T4-{code}", "T4_address", q, "short", None, gold, old, meta)
    # diacritics twins: a fixed subset stratified by cell, skipping items the eval linter
    # rejects once diacritics are removed (old and gold answers identical without diacritics)
    def nd_safe(it: dict) -> bool:
        tw = dict(it, meta=dict(it["meta"], has_diacritics=False))
        return not lint_item(tw)
    by_cell: dict[str, list[str]] = defaultdict(list)
    for code, it in items_by_code.items():
        if nd_safe(it):
            by_cell[cell(it["meta"]["province_changed"], it["meta"]["ward_changed"])].append(code)
    total = sum(len(v) for v in by_cell.values())
    twins: set[str] = set()
    alloc = {cl: round(N_T4_NODIAC * len(v) / total) for cl, v in by_cell.items()}
    diff = N_T4_NODIAC - sum(alloc.values())
    alloc[max(alloc, key=lambda k: len(by_cell[k]))] += diff
    for cl in sorted(by_cell):
        lst = sorted(by_cell[cl])
        rng_for(f"T4nd:{cl}").shuffle(lst)
        twins |= set(lst[: alloc[cl]])
    groups = []
    for code in sorted(items_by_code):
        it = items_by_code[code]
        grp = [it]
        if code in twins:
            addr = it["question"].split("Địa chỉ cũ: ", 1)[1].split(". Địa chỉ này", 1)[0]
            q2 = it["question"].replace(addr, nodiac(addr))
            tw = dict(it, id=f"{it['id']}-nd", question=q2,
                      meta=dict(it["meta"], has_diacritics=False, twin_id=it["id"]))
            it["meta"]["twin_id"] = it["id"]
            grp.append(tw)
        groups.append(grp)
    return groups


# ----------------------------------------------------------------------------- T3 existence

def build_t3(t: Tables, c: Ctx) -> list[list[dict]]:
    q_tmpl = "Hiện nay, {e} có phải là một đơn vị hành chính đang tồn tại không? Nếu có, đó là đơn vị hành chính cấp nào?"
    groups = []

    def add(iid: str, entity: str, gold: str, old: str | None, meta: dict) -> None:
        dis = [v for k, v in T3_CHOICES.items() if v != T3_CHOICES[gold]]
        ch, gl, ol = mcq(iid, T3_CHOICES[gold], dis, T3_CHOICES[old] if old and old != gold else None)
        base = dict(province_changed=None, ward_changed=None, change_type=None, old_province_code=None,
                    new_province_code=None, old_ward_code=None, new_ward_code=None, consistency_group=None,
                    has_diacritics=True, cue=None, cue_group=None)
        base.update(meta)
        base["t3_gold_kind"] = gold
        base["t3_exists"] = gold != "N"
        groups.append([item(iid, "T3_existence", q_tmpl.format(e=entity), "mcq", ch, gl, ol, base)])

    # provinces (all 63): absorbed -> no (old: tỉnh); kept/namesake -> yes (tỉnh)
    for p in sorted(t.provinces_old, key=lambda x: x["code"]):
        g = t.pnew[t.new_of_old_prov[p["code"]]]
        exists = key(p["short_name"]) == key(g["short_name"])
        add(f"T3-prov-{p['code']}", lower_prefix(p["name"]), "P" if exists else "N", "P",
            dict(entity_kind="province", depth="surface", province_changed=len(g["merged_from"]) > 1,
                 old_province_code=p["code"], new_province_code=g["code"], entity_name=p["name"],
                 new_province_name=g["name"]))

    # districts -> no (old: huyện level). Skip districts whose whole territory became one đặc khu.
    dpool: dict[str, list[str]] = defaultdict(list)
    for dd in sorted(t.districts_old, key=lambda x: x["code"]):
        wards = t.wards_old_by_district.get(dd["code"], [])
        if not dd.get("has_wards", True) or not wards:
            continue
        targets = {r["new_ward_code"] for w in wards for r in t.rows_by_old.get(w["code"], [])}
        if any(t.wnew[x]["type"] == "đặc khu" for x in targets):
            continue
        dpool[dd["type"]].append(dd["code"])
    for code in sorted(round_robin_sample(dpool, N_T3["district"], "T3:district")):
        dd = t.dold[code]
        p = t.pold[dd["province_code"]]
        g = t.pnew[t.new_of_old_prov[p["code"]]]
        survives = key(dd["short_name"]) in t.new_ward_keys_by_prov[g["code"]]
        add(f"T3-dist-{code}", f"{lower_prefix(dd['name'])} ({lower_prefix(p['name'])})", "N", "D",
            dict(entity_kind="district", depth="surface", old_province_code=p["code"], new_province_code=g["code"],
                 entity_name=dd["name"], old_district_code=code, name_survives_as_ward=survives))

    # new wards -> yes (cấp xã); old answer "no" when the namesake old province had no such ward
    npool: dict[str, list[str]] = defaultdict(list)
    for w in sorted(t.wards_new, key=lambda x: x["code"]):
        rows = t.rows_by_new.get(w["code"], [])
        if not rows or w["type"] == "đặc khu":
            continue
        g = t.pnew[w["province_code"]]
        ns = next(cc for cc in g["merged_from"] if key(t.pold[cc]["short_name"]) == key(g["short_name"]))
        existed = any(x["province_code"] == ns for x in t.old_ward_keys.get(key(w["short_name"]), []))
        if existed:
            continue  # keep only names that are new to the namesake province (old answer = no)
        npool[g["code"]].append(w["code"])
    for code in sorted(round_robin_sample(npool, N_T3["new_ward"], "T3:new_ward")):
        w = t.wnew[code]
        g = t.pnew[w["province_code"]]
        rows = t.rows_by_new[code]
        add(f"T3-neww-{code}", f"{lower_prefix(w['name'])} ({lower_prefix(g['name'])})", "W", "N",
            dict(entity_kind="new_ward", depth="deep", province_changed=len(g["merged_from"]) > 1,
                 ward_changed=any(r["change_type"] != "unchanged" for r in rows),
                 new_province_code=g["code"], new_ward_code=code, entity_name=w["name"],
                 new_ward_name=w["name"], new_province_name=g["name"]))

    # abolished old wards -> no (old: cấp xã): merged into a differently named ward and the
    # bare name exists nowhere among the new wards of the new province (preferably nowhere at all)
    apool: dict[str, list[str]] = defaultdict(list)
    for code, o in sorted(c.old.items()):
        r = o["rows"][0]
        if o["divided"] or r["change_type"] != "merged" or not r["name_changed"]:
            continue
        k = key(short_of(r["old_ward_name"]))
        if k in t.new_ward_keys_by_prov[r["new_province_code"]]:
            continue
        if t.new_ward_key_count.get(k, 0) > 0:
            continue  # stricter: absent nationwide
        if len([x for x in t.wards_old_by_district[r["old_district_code"]] if key(x["short_name"]) == k]) > 1:
            continue
        apool[o["cell"]].append(code)
    for code in sorted(round_robin_sample(apool, N_T3["abolished_ward"], "T3:abolished")):
        r = c.old[code]["rows"][0]
        w, d, p = old_addr_parts(t, r)
        add(f"T3-oldw-{code}", f"{lower_prefix(w)} ({lower_prefix(d)}, {lower_prefix(p)})", "N", "W",
            base_meta(r, entity_kind="abolished_ward", depth="deep", consistency_group=None, entity_name=w))

    # unchanged control wards -> yes (cấp xã)
    upool: dict[str, list[str]] = defaultdict(list)
    for code, o in sorted(c.old.items()):
        if o["cell"] in ("pc0_wc0", "pc1_wc0"):
            upool[o["cell"]].append(code)
    for code in sorted(round_robin_sample(upool, N_T3["unchanged_ward"], "T3:unchanged")):
        r = c.old[code]["rows"][0]
        w, d, p = old_addr_parts(t, r)
        add(f"T3-keepw-{code}", f"{lower_prefix(w)} ({lower_prefix(d)}, {lower_prefix(p)})", "W", "W",
            base_meta(r, entity_kind="unchanged_ward", depth="deep", consistency_group=None, entity_name=w))
    return groups
