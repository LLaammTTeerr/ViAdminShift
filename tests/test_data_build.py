"""Sanity checks for data/processed/ (run `uv run python -m viadmin.data.build` first)."""

from __future__ import annotations

import collections
import json
import unicodedata
from pathlib import Path

import pytest

from viadmin.data.build import NQ202
from viadmin.data.normalize import name_key

PROC = Path(__file__).resolve().parents[1] / "data" / "processed"

# Nghị quyết 202/2025/QH15: "11 tỉnh, thành phố không thực hiện sắp xếp là các tỉnh: Cao Bằng,
# Điện Biên, Hà Tĩnh, Lai Châu, Lạng Sơn, Nghệ An, Quảng Ninh, Thanh Hóa, Sơn La và thành phố
# Hà Nội, thành phố Huế."  (independent of the table in build.py on purpose)
UNCHANGED_11 = {
    "Tỉnh Cao Bằng", "Tỉnh Điện Biên", "Tỉnh Hà Tĩnh", "Tỉnh Lai Châu", "Tỉnh Lạng Sơn",
    "Tỉnh Nghệ An", "Tỉnh Quảng Ninh", "Tỉnh Thanh Hóa", "Tỉnh Sơn La",
    "Thành phố Hà Nội", "Thành phố Huế",
}
# NQ 202 Điều 1: resulting names of the 23 merged units (and their old components, by name)
MERGED_23 = {
    "Tỉnh Tuyên Quang": {"Hà Giang", "Tuyên Quang"},
    "Tỉnh Lào Cai": {"Yên Bái", "Lào Cai"},
    "Tỉnh Thái Nguyên": {"Bắc Kạn", "Thái Nguyên"},
    "Tỉnh Phú Thọ": {"Vĩnh Phúc", "Hòa Bình", "Phú Thọ"},
    "Tỉnh Bắc Ninh": {"Bắc Giang", "Bắc Ninh"},
    "Tỉnh Hưng Yên": {"Thái Bình", "Hưng Yên"},
    "Thành phố Hải Phòng": {"Hải Phòng", "Hải Dương"},
    "Tỉnh Ninh Bình": {"Hà Nam", "Nam Định", "Ninh Bình"},
    "Tỉnh Quảng Trị": {"Quảng Bình", "Quảng Trị"},
    "Thành phố Đà Nẵng": {"Đà Nẵng", "Quảng Nam"},
    "Tỉnh Quảng Ngãi": {"Kon Tum", "Quảng Ngãi"},
    "Tỉnh Gia Lai": {"Bình Định", "Gia Lai"},
    "Tỉnh Khánh Hòa": {"Ninh Thuận", "Khánh Hòa"},
    "Tỉnh Lâm Đồng": {"Đắk Nông", "Bình Thuận", "Lâm Đồng"},
    "Tỉnh Đắk Lắk": {"Phú Yên", "Đắk Lắk"},
    "Thành phố Hồ Chí Minh": {"Hồ Chí Minh", "Bà Rịa - Vũng Tàu", "Bình Dương"},
    "Tỉnh Đồng Nai": {"Bình Phước", "Đồng Nai"},
    "Tỉnh Tây Ninh": {"Long An", "Tây Ninh"},
    "Thành phố Cần Thơ": {"Cần Thơ", "Sóc Trăng", "Hậu Giang"},
    "Tỉnh Vĩnh Long": {"Bến Tre", "Trà Vinh", "Vĩnh Long"},
    "Tỉnh Đồng Tháp": {"Tiền Giang", "Đồng Tháp"},
    "Tỉnh Cà Mau": {"Bạc Liêu", "Cà Mau"},
    "Tỉnh An Giang": {"Kiên Giang", "An Giang"},
}
# island districts with no commune level before the reform -> đặc khu without any old ward
NO_OLD_WARD_NEW = {"11948", "19742", "20333", "21548", "26732"}


def load(name: str) -> list[dict]:
    path = PROC / name
    if not path.exists():
        pytest.skip(f"{path} missing; run `uv run python -m viadmin.data.build`")
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


@pytest.fixture(scope="module")
def t():
    return {n: load(f"{n}.jsonl") for n in
            ("provinces_old", "provinces_new", "districts_old", "wards_old", "wards_new", "ward_mapping")}


def test_counts(t):
    assert len(t["provinces_old"]) == 63
    assert len(t["provinces_new"]) == 34
    assert len(t["wards_new"]) == 3321
    assert collections.Counter(w["type"] for w in t["wards_new"]) == {"xã": 2621, "phường": 687, "đặc khu": 13}
    assert collections.Counter(p["type"] for p in t["provinces_new"]) == {"tỉnh": 28, "thành phố": 6}
    assert len(t["wards_old"]) == 10035  # official pre-reform commune count
    assert len(t["districts_old"]) == 696


def test_codes_unique(t):
    for name, key in [("provinces_old", "code"), ("provinces_new", "code"), ("districts_old", "code"),
                      ("wards_old", "code"), ("wards_new", "code")]:
        codes = [r[key] for r in t[name]]
        assert len(codes) == len(set(codes)), name
    pairs = [(m["old_ward_code"], m["new_ward_code"]) for m in t["ward_mapping"]]
    assert len(pairs) == len(set(pairs))


def test_code_formats(t):
    assert all(len(p["code"]) == 2 and p["code"].isdigit() for p in t["provinces_old"] + t["provinces_new"])
    assert all(len(d["code"]) == 3 and d["code"].isdigit() for d in t["districts_old"])
    assert all(len(w["code"]) == 5 and w["code"].isdigit() for w in t["wards_old"] + t["wards_new"])


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


def test_nfc_everywhere(t):
    for name, rows in t.items():
        for r in rows:
            for s in _strings(r):
                assert unicodedata.is_normalized("NFC", s), (name, s)
                assert s == s.strip() and "  " not in s and "\n" not in s, (name, s)
                assert "’" not in s, (name, s)


def test_new_province_names_match_resolution(t):
    names = {p["name"] for p in t["provinces_new"]}
    assert names == UNCHANGED_11 | set(MERGED_23)
    old_by_code = {p["code"]: p for p in t["provinces_old"]}
    for p in t["provinces_new"]:
        parts = {old_by_code[c]["short_name"] for c in p["merged_from"]}
        if p["name"] in UNCHANGED_11:
            assert len(p["merged_from"]) == 1
            assert name_key(old_by_code[p["merged_from"][0]]["name"]) == name_key(p["name"])
        else:
            assert {name_key(x) for x in parts} == {name_key(x) for x in MERGED_23[p["name"]]}, p["name"]


def test_merged_from_partitions_old_provinces(t):
    all_parts = [c for p in t["provinces_new"] for c in p["merged_from"]]
    assert sorted(all_parts) == sorted(p["code"] for p in t["provinces_old"])
    assert {p["code"] for p in t["provinces_new"] if len(p["merged_from"]) == 1} == \
           {c for c, (_, parts, _) in NQ202.items() if len(parts) == 1}


def test_merged_from_consistent_with_ward_mapping(t):
    derived = collections.defaultdict(set)
    for m in t["ward_mapping"]:
        derived[m["new_province_code"]].add(m["old_province_code"])
    for p in t["provinces_new"]:
        assert derived[p["code"]] == set(p["merged_from"]), p["code"]


def test_every_old_ward_maps(t):
    mapped = collections.defaultdict(set)
    for m in t["ward_mapping"]:
        mapped[m["old_ward_code"]].add(m["new_ward_code"])
    assert set(mapped) == {w["code"] for w in t["wards_old"]}
    assert all(len(v) >= 1 for v in mapped.values())


def test_every_new_ward_has_source(t):
    sourced = {m["new_ward_code"] for m in t["ward_mapping"]}
    missing = {w["code"] for w in t["wards_new"]} - sourced
    assert missing == NO_OLD_WARD_NEW
    assert all(w["type"] == "đặc khu" for w in t["wards_new"] if w["code"] in NO_OLD_WARD_NEW)


def test_mapping_consistent_with_tables(t):
    wo = {w["code"]: w for w in t["wards_old"]}
    wn = {w["code"]: w for w in t["wards_new"]}
    do = {d["code"]: d for d in t["districts_old"]}
    pn = {p["code"]: p for p in t["provinces_new"]}
    po = {p["code"]: p for p in t["provinces_old"]}
    for m in t["ward_mapping"]:
        o, n = wo[m["old_ward_code"]], wn[m["new_ward_code"]]
        assert m["old_ward_name"] == o["name"] and m["old_ward_type"] == o["type"]
        assert m["old_ward_name_alt"] == o["name_alt"]
        assert m["old_district_code"] == o["district_code"] and m["old_province_code"] == o["province_code"]
        assert m["old_district_name"] == do[o["district_code"]]["name"]
        assert m["old_province_name"] == po[o["province_code"]]["name"]
        assert m["new_ward_name"] == n["name"] and m["new_ward_type"] == n["type"]
        assert m["new_province_code"] == n["province_code"]
        assert m["new_province_name"] == pn[n["province_code"]]["name"]
        # whole provinces merged: an old ward always lands in its old province's successor
        assert m["old_province_code"] in pn[m["new_province_code"]]["merged_from"]


def test_types(t):
    assert {w["type"] for w in t["wards_old"]} == {"phường", "xã", "thị trấn"}
    assert {d["type"] for d in t["districts_old"]} == {"quận", "huyện", "thị xã", "thành phố"}
    for rows in (t["wards_old"], t["wards_new"]):
        for w in rows:
            assert w["name"].lower().startswith(w["type"] + " "), w
            assert w["name"][len(w["type"]) + 1:] == w["short_name"]


def test_change_type_definitions(t):
    targets = collections.defaultdict(set)
    sources = collections.defaultdict(set)
    for m in t["ward_mapping"]:
        targets[m["old_ward_code"]].add(m["new_ward_code"])
        sources[m["new_ward_code"]].add(m["old_ward_code"])
    for m in t["ward_mapping"]:
        nt, ns = len(targets[m["old_ward_code"]]), len(sources[m["new_ward_code"]])
        assert m["n_new_targets"] == nt and m["n_old_sources"] == ns
        assert m["is_partial"] == (nt > 1)
        if nt > 1:
            assert m["change_type"] == "divided"
        elif ns > 1:
            assert m["change_type"] == "merged"
        else:
            assert m["change_type"] in ("unchanged", "renamed")
        if m["change_type"] == "unchanged":
            assert m["name_changed"] == m["spelling_variant"]
        if m["change_type"] == "renamed":
            assert m["name_changed"]
        assert m["ward_changed"] == (m["change_type"] != "unchanged")


def test_province_changed(t):
    pn = {p["code"]: p for p in t["provinces_new"]}
    unchanged_codes = {p["code"] for p in t["provinces_new"] if p["name"] in UNCHANGED_11}
    assert len(unchanged_codes) == 11
    for m in t["ward_mapping"]:
        assert m["province_changed"] == (m["new_province_code"] not in unchanged_codes)
        assert m["province_changed"] == (len(pn[m["new_province_code"]]["merged_from"]) > 1)


def test_all_2x2_cells_populated(t):
    cells = collections.Counter((m["province_changed"], m["ward_changed"]) for m in t["ward_mapping"])
    assert set(cells) == {(a, b) for a in (False, True) for b in (False, True)}
    assert min(cells.values()) >= 30


def test_sources_and_confidence(t):
    from viadmin.data.build import RESOLUTION_ADDED_PAIRS
    for m in t["ward_mapping"]:
        pair = (m["old_ward_code"], m["new_ward_code"])
        # "nso" is the backbone; the only rows without it are hand-checked pairs added from the resolution
        assert m["sources"][0] == ("resolution" if pair in RESOLUTION_ADDED_PAIRS else "nso"), m
        assert m["confidence"] in ("high", "single", "conflict")
        lineages = sum(x in m["sources"] for x in ("nso", "vietnamadminunits", "resolution"))
        assert (m["confidence"] == "high") == (lineages >= 2)
    conf = collections.Counter(m["confidence"] for m in t["ward_mapping"])
    assert conf["high"] / len(t["ward_mapping"]) > 0.99


def test_spot_checked_rows(t):
    """A few rows verified by hand against the UBTVQH resolutions (docs/data_report.md)."""
    idx = collections.defaultdict(set)
    for m in t["ward_mapping"]:
        idx[(m["old_province_name"], m["old_district_name"], m["old_ward_name"])].add(m["new_ward_name"])
    assert idx[("Thành phố Hà Nội", "Huyện Mê Linh", "Xã Văn Khê")] == \
        {"Xã Ô Diên", "Xã Mê Linh", "Xã Yên Lãng", "Xã Tiến Thắng"}          # NQ 1656 k.107,118-120
    assert idx[("Tỉnh Hà Nam", "Thị xã Duy Tiên", "Phường Hoàng Đông")] == {"Phường Duy Hà", "Phường Hà Nam"}
    assert idx[("Tỉnh Tuyên Quang", "Huyện Yên Sơn", "Xã Phú Thịnh")] == {"Xã Thái Bình"}  # NQ 1684 k.28
    assert idx[("Tỉnh Tuyên Quang", "Huyện Yên Sơn", "Xã Công Đa")] == {"Xã Trung Sơn"}    # NQ 1684 k.27
    assert idx[("Tỉnh Cao Bằng", "Huyện Quảng Hòa", "Xã Mỹ Hưng")] == {"Xã Phục Hòa"}      # NQ 1657 k.38
    assert idx[("Tỉnh Tiền Giang", "Thành phố Mỹ Tho", "Phường 4")] == {"Phường Đạo Thạnh"}  # NQ 1663 k.84
    assert idx[("Thành phố Hồ Chí Minh", "Quận 1", "Phường Bến Thành")] == {"Phường Bến Thành"}


def _by_code(t):
    rows = collections.defaultdict(list)
    for m in t["ward_mapping"]:
        rows[m["old_ward_code"]].append(m)
    return rows


def test_hoa_thang_split_regression(t):
    """NQ 1671/NQ-UBTVQH15 k.46 + k.51: xã Hòa Thắng (Bắc Bình) was split between Hồng Thái and Hòa
    Thắng; the NSO table has only Hòa Thắng -> Hòa Thắng ('Nhập toàn bộ')."""
    rows = _by_code(t)["23053"]
    assert {m["new_ward_name"] for m in rows} == {"Xã Hòa Thắng", "Xã Hồng Thái"}
    assert all(m["change_type"] == "divided" and m["is_partial"] and m["n_new_targets"] == 2 for m in rows)
    added = next(m for m in rows if m["new_ward_code"] == "23041")
    assert added["sources"][0] == "resolution" and "nso" not in added["sources"]
    assert added["confidence"] == "high"
    comp = {m["old_ward_name"] for m in t["ward_mapping"] if m["new_ward_code"] == "23041"}
    assert comp == {"Xã Phan Thanh", "Xã Hồng Thái", "Xã Hòa Thắng"}
    assert all(m["n_old_sources"] == 3 for m in t["ward_mapping"] if m["new_ward_code"] == "23041")


def test_old_names_follow_resolution(t):
    """Registry vs NSO spelling disagreements are decided by the resolution text."""
    wo = {w["code"]: w for w in t["wards_old"]}
    expect = {
        "12664": "Xã Kim Trung",          # NQ 1666 k.71 (registry: Kim Chung)
        "18007": "Xã Hưng Yên Nam",       # NQ 1678 k.27 (registry: Hưng Yên; sibling 18008 Hưng Yên Bắc)
        "04456": "Thị trấn Mù Cang Chải",  # NQ 1673 (registry: Mù Căng Chải)
        "23458": "Xã Măng Bút",           # NQ 1677 (registry: Măng Buk)
        "03244": "Xã Xá Nhè",             # manual override, NQ 1661 k.20
        # registry spelling kept: the resolution uses it
        "09383": "Phường Trang Hạ",
        "24643": "Xã Đắk Wil",
        "22267": "Xã Hòa Tân Đông",       # NSO says phường; NQ 1660 k.94 says xã
        "19780": "Phường Phường Đúc",     # ward named "Phường Đúc" (NQ 1675 k.15)
    }
    for code, name in expect.items():
        assert wo[code]["name"] == name, (code, wo[code]["name"])
    rows = _by_code(t)
    assert rows["12664"][0]["old_ward_name_alt"] == "Xã Kim Chung"
    assert rows["03244"][0]["old_ward_name_alt"] is None   # verified-wrong registry value is no alias
    # surface name unchanged when the resolution spells old and new identically (NQ 1687 k.78)
    an_qui = next(m for m in t["ward_mapping"] if m["old_ward_name"] == "Xã An Qui")
    assert an_qui["new_ward_name"] == "Xã An Qui" and not an_qui["name_changed"]
    for m in t["ward_mapping"]:
        if m["old_ward_name_alt"] is not None:
            assert name_key(m["old_ward_name_alt"]) != name_key(m["old_ward_name"])
    assert not any(w["name"].startswith("Thị Trấn ") for w in t["wards_old"])


def test_surface_answer_changed(t):
    for m in t["ward_mapping"]:
        assert m["name_changed"] == (name_key(m["old_ward_name"]) != name_key(m["new_ward_name"]))
        assert m["province_name_changed"] == (name_key(m["old_province_name"]) != name_key(m["new_province_name"]))
        assert m["surface_answer_changed"] == (m["name_changed"] or m["province_name_changed"])
        if not m["province_changed"]:
            assert not m["province_name_changed"]
        if not m["ward_changed"] and not m["province_changed"] and not m["spelling_variant"]:
            assert not m["surface_answer_changed"]
    # province merged but kept the old province's name (old Tuyên Quang -> new Tuyên Quang)
    tq = [m for m in t["ward_mapping"] if m["old_province_code"] == "08"]
    assert tq and all(m["province_changed"] and not m["province_name_changed"] for m in tq)


def test_bando_mentions_spacing_insensitive(t):
    rows = _by_code(t)
    for code in ("00226", "22225", "22228"):   # Văn Miếu - Quốc Tử Giám, EaBar, EaBia
        assert all(m["bando_mentions_old_ward"] for m in rows[code]), code
    false = [m for m in t["ward_mapping"] if m["bando_mentions_old_ward"] is False]
    assert len(false) <= 15


def test_resolution_parser():
    from viadmin.data.resolutions import RES_DIR, clause_for

    if not (RES_DIR / "1671.html").exists():
        pytest.skip("resolution texts missing")
    k, text, items = clause_for("1671", "Hồng Thái")
    assert k == 46
    assert [(i["name"], i["mode"]) for i in items] == [("Phan Thanh", "whole"), ("Hồng Thái", "whole"),
                                                        ("Hòa Thắng", "part")]
    k, _, items = clause_for("1684", "Hà Giang 2")
    assert {i["name"]: i["mode"] for i in items}["Phong Quang"] == "whole"   # glued "Phong Quangthành"
    k, _, items = clause_for("1654", "Mỹ Hòa Hưng")                        # communes kept as-is
    assert "Tiên Hải" in [i["name"] for i in items]
