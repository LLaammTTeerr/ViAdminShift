"""Canonicalise the 1/7/2025 administrative-reform data into data/processed/.

Run:  uv run python -m viadmin.data.build

Inputs (all under data/raw/, see each SOURCE.md):
  nso_conversion/BangChuyendoiDVHCmoi_cu_final.xlsx   lineage A (official NSO conversion table) -- BACKBONE
  vietnamadminunits/...                               lineage B (sapnhap.bando.com.vn-derived converter)
  undertheseanlp_address/mapping.json                 lineage B derivative (copy of vietnamadminunits 1.0.4)
  vietaddr/legacy-map.json                            lineage A derivative (provinces.open-api.vn)
  vietnamadminunits/data/raw/danhmuchanhchinh.gso.gov.vn_*_2025-07-18.csv   pre-reform GSO registry
  vietnamadminunits/data/raw/production.cas.so_*.json new communes + resolution numbers
  vietnamadminunits/data/raw/sapnhap.bando.com.vn_ward_*.csv  composition texts (adjudication only)
  ubtvqh_resolutions_hoatieu/html/<NQ>.html            UBTVQH15 ward-level resolutions (old-name spelling,
                                                       checks; see viadmin.data.resolutions)

Outputs: the tables defined in docs/SPEC.md plus
  data/processed/build_stats.json            counts used by docs/data_report.md
  data/processed/crosscheck_issues.jsonl     every cross-source disagreement / data fix
"""

from __future__ import annotations

import collections
import csv
import json
import re
import sys
from pathlib import Path

from viadmin.data.normalize import (
    loose_key,
    name_key,
    nfc,
    split_district,
    split_province,
    split_ward,
)
from viadmin.data.resolutions import clause_for, mentions
from viadmin.data.xlsx import read_xlsx
from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"

NSO_XLSX = RAW / "nso_conversion" / "BangChuyendoiDVHCmoi_cu_final.xlsx"
NSO_SHEET = "Tổng hợp_không merge "
VNAU = RAW / "vietnamadminunits" / "data"
GSO_WARDS = VNAU / "raw" / "danhmuchanhchinh.gso.gov.vn_ward_2025-07-18.csv"
GSO_DISTRICTS = VNAU / "raw" / "danhmuchanhchinh.gso.gov.vn_district_2025-07-18.csv"
VNAU_CONVERT = VNAU / "processed" / "convert_legacy_2025_with_location_and_default_ward.csv"
VNAU_NEW = VNAU / "processed" / "2025_34-province-3221-ward_with_location.csv"
CAS_SO = VNAU / "raw" / "production.cas.so_3221_wards_2025-08-05.json"
BANDO_WARDS = VNAU / "raw" / "sapnhap.bando.com.vn_ward_2025-07-17.csv"
UTS = RAW / "undertheseanlp_address" / "mapping.json"
VIETADDR = RAW / "vietaddr" / "legacy-map.json"
VIETADDR_UNITS = RAW / "vietaddr" / "vn-units.json"

# ---------------------------------------------------------------------------
# Province-level facts from Nghị quyết 202/2025/QH15 (Điều 1), transcribed by hand
# (text checked against the reproduction on baolaocai.vn and the Cần Thơ PBGDPL
# portal; see docs/data_report.md). Keys: new province GSO code -> (official name,
# old province codes merged).  The new province takes the code of one of its parts.
# `seat` = old province whose current centre hosts the new provincial political-
# administrative centre (Nghị quyết 60-NQ/TW; same as sapnhap.bando.com.vn "trungtamhc").
# ---------------------------------------------------------------------------
NQ202 = {
    # 11 provinces NOT rearranged (NQ 202: "11 tỉnh, thành phố không thực hiện sắp xếp")
    "01": ("Thành phố Hà Nội", ["01"], "01"),
    "04": ("Tỉnh Cao Bằng", ["04"], "04"),
    "11": ("Tỉnh Điện Biên", ["11"], "11"),
    "12": ("Tỉnh Lai Châu", ["12"], "12"),
    "14": ("Tỉnh Sơn La", ["14"], "14"),
    "20": ("Tỉnh Lạng Sơn", ["20"], "20"),
    "22": ("Tỉnh Quảng Ninh", ["22"], "22"),
    "38": ("Tỉnh Thanh Hóa", ["38"], "38"),
    "40": ("Tỉnh Nghệ An", ["40"], "40"),
    "42": ("Tỉnh Hà Tĩnh", ["42"], "42"),
    "46": ("Thành phố Huế", ["46"], "46"),
    # 23 merged units
    "08": ("Tỉnh Tuyên Quang", ["02", "08"], "08"),          # Hà Giang + Tuyên Quang
    "15": ("Tỉnh Lào Cai", ["10", "15"], "15"),              # Lào Cai + Yên Bái; seat Yên Bái
    "19": ("Tỉnh Thái Nguyên", ["06", "19"], "19"),          # Bắc Kạn + Thái Nguyên
    "25": ("Tỉnh Phú Thọ", ["17", "25", "26"], "25"),        # Hòa Bình + Phú Thọ + Vĩnh Phúc
    "24": ("Tỉnh Bắc Ninh", ["24", "27"], "24"),             # Bắc Giang + Bắc Ninh; seat Bắc Giang
    "33": ("Tỉnh Hưng Yên", ["33", "34"], "33"),             # Hưng Yên + Thái Bình
    "31": ("Thành phố Hải Phòng", ["30", "31"], "31"),       # Hải Dương + Hải Phòng
    "37": ("Tỉnh Ninh Bình", ["35", "36", "37"], "37"),      # Hà Nam + Nam Định + Ninh Bình
    "44": ("Tỉnh Quảng Trị", ["44", "45"], "44"),            # Quảng Bình + Quảng Trị; seat Quảng Bình
    "48": ("Thành phố Đà Nẵng", ["48", "49"], "48"),         # Đà Nẵng + Quảng Nam
    "51": ("Tỉnh Quảng Ngãi", ["51", "62"], "51"),           # Quảng Ngãi + Kon Tum
    "52": ("Tỉnh Gia Lai", ["52", "64"], "52"),              # Bình Định + Gia Lai; seat Bình Định
    "56": ("Tỉnh Khánh Hòa", ["56", "58"], "56"),            # Khánh Hòa + Ninh Thuận
    "68": ("Tỉnh Lâm Đồng", ["60", "67", "68"], "68"),       # Bình Thuận + Đắk Nông + Lâm Đồng
    "66": ("Tỉnh Đắk Lắk", ["54", "66"], "66"),              # Phú Yên + Đắk Lắk
    "79": ("Thành phố Hồ Chí Minh", ["74", "77", "79"], "79"),  # Bình Dương + BR-VT + HCM
    "75": ("Tỉnh Đồng Nai", ["70", "75"], "75"),             # Bình Phước + Đồng Nai
    "80": ("Tỉnh Tây Ninh", ["72", "80"], "80"),             # Tây Ninh + Long An; seat Long An
    "92": ("Thành phố Cần Thơ", ["92", "93", "94"], "92"),   # Cần Thơ + Hậu Giang + Sóc Trăng
    "86": ("Tỉnh Vĩnh Long", ["83", "84", "86"], "86"),      # Bến Tre + Trà Vinh + Vĩnh Long
    "82": ("Tỉnh Đồng Tháp", ["82", "87"], "82"),            # Tiền Giang + Đồng Tháp; seat Tiền Giang
    "96": ("Tỉnh Cà Mau", ["95", "96"], "96"),               # Bạc Liêu + Cà Mau
    "91": ("Tỉnh An Giang", ["89", "91"], "91"),             # An Giang + Kiên Giang; seat Kiên Giang
}
UNCHANGED_PROVINCES = {c for c, (_, parts, _) in NQ202.items() if len(parts) == 1}

# Old province display names: the GSO registry writes "Tỉnh Hoà Bình"; NQ 202 writes "Hòa Bình".
OLD_PROVINCE_NAME_FIX = {"17": "Tỉnh Hòa Bình"}

REGISTRY_TYPE_CONFLICTS: list[dict] = []

# Manual corrections of the pre-reform registry, each verified against the resolution text.
# code -> (corrected full name, evidence)
OLD_WARD_NAME_OVERRIDES = {
    # registry (2025-07-18 scrape) still lists "Xã Tiên Sơn"; NQ 1674/NQ-UBTVQH15 khoản 102 and the
    # NSO conversion table both say "phường Tiên Sơn" (upgraded before 1/7/2025).
    "13369": ("Phường Tiên Sơn", "NQ 1674/NQ-UBTVQH15 Điều 1 khoản 102"),
    # registry shows the code's NEW name; NQ 1661/NQ-UBTVQH15 khoản 20 merges "xã Xá Nhè, Mường Đun
    # và Phình Sáng" into the new "xã Sáng Nhè" (NSO table and vietnamadminunits also say Xá Nhè).
    "03244": ("Xã Xá Nhè", "NQ 1661/NQ-UBTVQH15 Điều 1 khoản 20"),
}

# Registry spelling kept although the NSO spelling seems to match the resolution better (parser
# limitation); code -> reason.
OLD_WARD_KEEP_REGISTRY = {
    "19780": "the ward's name is 'Phường Đúc' (NQ 1675/NQ-UBTVQH15 khoản 15: 'các phường Phú Hội, Phú "
             "Nhuận, Phường Đúc, ...'), so the full name is 'Phường Phường Đúc'; NSO drops the doubled prefix",
}

# (old ward, new ward) pairs that the NSO table LACKS but the resolution states; each checked by hand
# against the resolution text (data/raw/ubtvqh_resolutions_hoatieu) and present in lineage B.
RESOLUTION_ADDED_PAIRS = {
    ("23053", "23041"): (
        "1671/NQ-UBTVQH15 Điều 1 khoản 46",
        "khoản 46: '... xã Phan Thanh, xã Hồng Thái và một phần diện tích tự nhiên của xã Hòa Thắng thành xã "
        "mới có tên gọi là xã Hồng Thái'; khoản 51: 'phần còn lại của xã Hòa Thắng sau khi sắp xếp theo quy "
        "định tại khoản 46' -> xã Hòa Thắng. NSO has only Hòa Thắng -> Hòa Thắng ('Nhập toàn bộ').",
    ),
}
# NSO pairs checked by hand against the resolution text (adds the "resolution" source).
RESOLUTION_VERIFIED_PAIRS = {
    ("09013", "09817"): "1656/NQ-UBTVQH15 Điều 1 khoản 107: 'một phần diện tích tự nhiên của xã Văn Khê' -> xã Ô Diên",
    ("23053", "23053"): "1671/NQ-UBTVQH15 Điều 1 khoản 51: 'phần còn lại của xã Hòa Thắng' -> xã Hòa Thắng",
}

SRC_NSO, SRC_VNAU, SRC_UTS, SRC_VIETADDR = "nso", "vietnamadminunits", "undertheseanlp", "vietaddr"
SRC_RES = "resolution"  # pair checked by hand against the UBTVQH resolution text (see above)


def squash_key(s: str) -> str:
    """name_key without spaces, hyphens and dashes (bando writes "Ea Bar" for the registry's "EaBar")."""
    return re.sub(r"[\s\-\u2013]+", "", name_key(s))


def short(full: str) -> str:
    try:
        return split_ward(full)[1]
    except ValueError:
        return nfc(full)


def wtype_or_none(full: str) -> str | None:
    try:
        return split_ward(full)[0]
    except ValueError:
        return None


def code5(x: str) -> str:
    x = nfc(x)
    if not x:
        return ""
    return str(int(float(x))).zfill(5)


def code3(x: str) -> str:
    x = nfc(x)
    return str(int(float(x))).zfill(3) if x else ""


def code2(x: str) -> str:
    x = nfc(x)
    return str(int(float(x))).zfill(2) if x else ""


def paren_code(s: str) -> str:
    m = re.search(r"\((\d+)\)\s*$", nfc(s))
    if not m:
        raise ValueError(f"no (code) in {s!r}")
    return m.group(1)


def strip_paren(s: str) -> str:
    return nfc(re.sub(r"\(\d+\)\s*$", "", nfc(s)))


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def load_old_registry():
    """Pre-reform GSO registry (state immediately before 1/7/2025)."""
    provinces, districts, wards = {}, {}, {}
    with GSO_DISTRICTS.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            dcode = code3(r["Mã"])
            dtype, dshort = split_district(r["Tên"])
            districts[dcode] = {
                "code": dcode,
                "name": nfc(r["Tên"]),
                "short_name": dshort,
                "type": dtype,
                "province_code": code2(r["Mã TP"]),
            }
    with GSO_WARDS.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            pcode = code2(r["Mã TP"])
            pname = OLD_PROVINCE_NAME_FIX.get(pcode, nfc(r["Tỉnh / Thành Phố"]))
            ptype, pshort = split_province(pname)
            provinces[pcode] = {"code": pcode, "name": pname, "short_name": pshort, "type": ptype}
            wcode = code5(r["Mã"])
            wname = nfc(r["Tên"])
            # registry abbreviates "Nông trường" (state farm) as "NT"/"N.T"; expand (NSO spells it out)
            wname = re.sub(r"^Thị trấn N\.?T\.? ", "Thị trấn Nông trường ", wname)
            wname = re.sub(r"^Thị Trấn ", "Thị trấn ", wname)  # 4 registry rows capitalise the prefix
            if code5(r["Mã"]) in OLD_WARD_NAME_OVERRIDES:
                wname = OLD_WARD_NAME_OVERRIDES[code5(r["Mã"])][0]
            wtype, wshort = split_ward(wname)
            if wtype != nfc(r["Cấp"]).lower():
                # registry inconsistency (name prefix vs 'Cấp'); the name prefix is authoritative
                REGISTRY_TYPE_CONFLICTS.append({"code": code5(r["Mã"]), "name": nfc(r["Tên"]), "cap": nfc(r["Cấp"])})
            wards[wcode] = {
                "code": wcode,
                "name": wname,
                "short_name": wshort,
                "type": wtype,
                "district_code": code3(r["Mã QH"]),
                "province_code": pcode,
            }
    for w in wards.values():
        assert districts[w["district_code"]]["province_code"] == w["province_code"], w
    return provinces, districts, wards


def load_nso(issues: list[dict]):
    """Rows of the official NSO conversion table (sheet 'không merge')."""
    rows = read_xlsx(str(NSO_XLSX))[NSO_SHEET]
    header = [nfc(x) for x in rows[1]]
    assert header[:8] == [
        "Tỉnh, thành phố", "Tên Xã mới", "Mã Xã mới", "Tên Xã cũ", "Mã Xã cũ",
        "Ghi chú", "Quận/huyện", "Tỉnh cũ",
    ], header
    out = []
    for i, r in enumerate(rows[2:], start=3):
        r = (r + [""] * 8)[:8]
        if not nfc(r[2]):
            continue  # province banner rows
        out.append({
            "xlsx_row": i,
            "new_province_code": paren_code(r[0]),
            "new_province_name": strip_paren(r[0]),
            "new_ward_name": nfc(r[1]),
            "new_ward_code": code5(r[2]),
            "old_ward_name": nfc(r[3]),
            "old_ward_code": code5(r[4]),
            "note": nfc(r[5]),
            "old_district_code": paren_code(r[6]) if nfc(r[6]) else "",
            "old_district_name": strip_paren(r[6]),
            "old_province_code": paren_code(r[7]) if nfc(r[7]) else "",
        })
    return out


class OldWardIndex:
    """Resolve (claimed code, name, district) to a registry old-ward code."""

    def __init__(self, wards_old: dict):
        # private snapshot: matching always uses the REGISTRY spelling, even after the build
        # replaces some names by the resolution's spelling (canonicalise_old_names)
        self.wards = {c: dict(w) for c, w in wards_old.items()}
        self.by_district = collections.defaultdict(list)
        for w in self.wards.values():
            self.by_district[w["district_code"]].append(w)

    def resolve(self, code: str, name: str, district_code: str) -> tuple[str | None, str]:
        """Returns (code, status); status in ok | spelling | fixed_by_name | kept_code | unresolved."""
        reg = self.wards.get(code) if code else None
        sn = loose_key(short(name))
        if reg is not None and reg["district_code"] == district_code:
            rs = loose_key(reg["short_name"])
            if rs == sn:
                return code, ("ok" if name_key(reg["name"]) == name_key(name) else "spelling")
            if fuzz.ratio(rs, sn) >= 75:
                return code, "spelling"
        cands = [w["code"] for w in self.by_district.get(district_code, []) if loose_key(w["short_name"]) == sn]
        if len(cands) == 1:
            return cands[0], "fixed_by_name" if code else "ok"
        if reg is not None and reg["district_code"] == district_code:
            return code, "kept_code"
        return None, "unresolved"


def resolve_nso_old_codes(nso_rows, idx: "OldWardIndex", issues):
    """The NSO table occasionally carries the wrong old-ward code (copy errors) or an
    outdated / misspelt old name. Validate every (old code, old name, district) against
    the GSO registry; if the name does not fit the code, look the name up inside the
    stated old district."""
    fixed = []
    for r in nso_rows:
        if not r["old_ward_code"]:
            continue
        code, status = idx.resolve(r["old_ward_code"], r["old_ward_name"], r["old_district_code"])
        reg = idx.wards.get(code) if code else None
        base = {"xlsx_row": r["xlsx_row"], "nso_code": r["old_ward_code"], "nso_name": r["old_ward_name"],
                "new_ward_code": r["new_ward_code"], "new_ward_name": r["new_ward_name"]}
        if status == "unresolved":
            raise SystemExit(f"Cannot resolve NSO old ward {r}")
        if status in ("ok", "spelling") and wtype_or_none(r["old_ward_name"]) not in (None, reg["type"]):
            issues.append(dict(kind="nso_old_type_differs_from_registry", registry_name=reg["name"], **base))
        elif status == "spelling":
            issues.append(dict(kind="nso_old_name_spelling_differs_from_registry", registry_name=reg["name"], **base))
        elif status == "fixed_by_name":
            wrong = idx.wards.get(r["old_ward_code"])
            issues.append(dict(kind="nso_old_code_fixed", fixed_code=code,
                               nso_code_registry_name=wrong["name"] if wrong else None, **base))
            r["old_ward_code"] = code
            fixed.append(r)
        elif status == "kept_code":
            issues.append(dict(kind="nso_old_name_differs_code_kept", registry_name=reg["name"], **base))
    return fixed


def canonicalise_old_names(wards_old: dict, nso_rows: list[dict], new_wards: dict, issues: list[dict]):
    """Choose the canonical spelling of each old ward name.

    Rule: registry (GSO) and NSO agree -> keep it. They disagree -> the UBTVQH resolution decides:
    the spelling named in the resolution clause(s) that form the ward's new unit(s) wins (exact item
    match first, whole-word mention as fallback; a unit-type change is adopted only when the clause
    states that type). Undecided -> registry kept. Mutates `wards_old` in place and returns
    {old code: alternative spelling} (the non-canonical one; never a verified-wrong registry name).
    """
    nso_names = collections.defaultdict(set)
    targets = collections.defaultdict(set)
    for r in nso_rows:
        nso_names[r["old_ward_code"]].add(r["old_ward_name"])
        targets[r["old_ward_code"]].add(r["new_ward_code"])
    alt: dict[str, str] = {}
    decisions = collections.Counter()
    for code in sorted(nso_names):
        w = wards_old[code]
        others = sorted({n for n in nso_names[code]
                         if name_key(n) != name_key(w["name"]) and wtype_or_none(n) is not None})
        if not others:
            continue
        if len(others) > 1:
            issues.append({"kind": "nso_old_name_several_spellings", "code": code, "names": others})
        nso_name = others[0]
        ntype, nshort = split_ward(nso_name)
        reg_hit = nso_hit = reg_m = nso_m = False
        evidence = []
        for nc in sorted(targets[code]):
            nw = new_wards[nc]
            if not nw.get("resolution"):
                continue
            cl = clause_for(nw["resolution"].split("/")[0], nw["short_name"])
            if cl is None:
                continue
            k, text, items = cl
            evidence.append(f"{nw['resolution']} Điều 1 khoản {k}")
            for it in items:
                tok, ty = name_key(it["name"]), it["type"]
                if tok == name_key(w["short_name"]) and ty in (None, w["type"]):
                    reg_hit = True
                if tok == name_key(nshort) and (ty == ntype or (ty is None and ntype == w["type"])):
                    nso_hit = True
            reg_m |= mentions(text, w["short_name"])
            nso_m |= mentions(text, nshort) and ntype == w["type"]
        base = {"code": code, "registry_name": w["name"], "nso_name": nso_name, "resolution_clauses": evidence}
        if code in OLD_WARD_KEEP_REGISTRY:
            decision = "registry_manual"
        elif code in OLD_WARD_NAME_OVERRIDES:
            decision = "registry_override"
        elif nso_hit and not reg_hit:
            decision = "nso"
        elif reg_hit and not nso_hit:
            decision = "registry"
        elif not reg_hit and not nso_hit and nso_m and not reg_m:
            decision = "nso"
        elif not reg_hit and not nso_hit and reg_m and not nso_m:
            decision = "registry"
        else:
            decision = "undecided_registry_kept"
        decisions[decision] += 1
        if decision == "nso":
            alt[code] = w["name"]
            w["name"], w["short_name"], w["type"] = nso_name, nshort, ntype
            issues.append(dict(kind="old_ward_name_from_resolution", **base))
        else:
            alt[code] = nso_name
            issues.append(dict(kind="old_ward_name_registry_kept", decision=decision,
                               reason=OLD_WARD_KEEP_REGISTRY.get(code), **base))
    # canonical name absent from every clause of the ward's new unit(s): documented, not changed
    not_found = 0
    for code, w in sorted(wards_old.items()):
        texts = []
        for nc in sorted(targets.get(code, ())):
            nw = new_wards[nc]
            cl = clause_for(nw["resolution"].split("/")[0], nw["short_name"]) if nw.get("resolution") else None
            if cl is not None:
                texts.append((f"{nw['resolution']} Điều 1 khoản {cl[0]}", cl[1]))
        if texts and not any(mentions(t, w["short_name"]) for _, t in texts):
            not_found += 1
            issues.append({"kind": "old_ward_name_not_in_resolution_clause", "code": code, "name": w["name"],
                           "alt": alt.get(code), "clauses": [e for e, _ in texts]})
    return alt, dict(decisions), not_found


def load_new_wards_checks():
    """Independent lists of the 3,321 new communes for name/code verification."""
    cas = json.loads(CAS_SO.read_text(encoding="utf-8"))["communes"]
    cas_by_code = {code5(c["code"]): c for c in cas}
    vnau_new = {}
    with VNAU_NEW.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            vnau_new[code5(r["wardCode"])] = r
    va = json.loads(VIETADDR_UNITS.read_text(encoding="utf-8"))
    va_by_code = {code5(w["code"]): w for w in va["wards"]}
    return cas_by_code, vnau_new, va_by_code


def load_vnau():
    rows = []
    with VNAU_CONVERT.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def load_uts():
    return json.loads(UTS.read_text(encoding="utf-8"))


def load_vietaddr():
    d = json.loads(VIETADDR.read_text(encoding="utf-8"))
    fix = {code5(k): code5(v) for k, v in d.get("new_code_fix", {}).items()}
    pairs = set()
    for old, (new, _dist) in d["wards"].items():
        pairs.add((code5(old), fix.get(code5(new), code5(new))))
    for old, (news, _dist) in d["split"].items():
        for new in news:
            pairs.add((code5(old), fix.get(code5(new), code5(new))))
    return pairs


def load_bando():
    out = {}
    with BANDO_WARDS.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            prov = nfc(r["tentinh"])
            prov = re.sub(r"^(tỉnh|thành phố|thủ đô)\s+", "", prov, flags=re.I)
            full = f"{nfc(r['loai'])} {nfc(r['tenhc'])}"
            out[(name_key(prov), name_key(full))] = nfc(r["truocsapnhap"])
    return out


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def main() -> int:
    issues: list[dict] = []
    stats: dict = {}

    provinces_old, districts_old, wards_old = load_old_registry()
    assert len(provinces_old) == 63, len(provinces_old)
    stats["registry_type_conflicts"] = REGISTRY_TYPE_CONFLICTS

    nso_rows = load_nso(issues)
    stats["nso_data_rows"] = len(nso_rows)
    no_old = [r for r in nso_rows if not r["old_ward_code"]]
    stats["nso_rows_without_old_ward"] = [
        {k: r[k] for k in ("new_ward_code", "new_ward_name", "old_ward_name", "note", "old_district_name")}
        for r in no_old
    ]
    nso_rows = [r for r in nso_rows if r["old_ward_code"]]
    idx = OldWardIndex(wards_old)
    fixed = resolve_nso_old_codes(nso_rows, idx, issues)
    stats["nso_old_code_fixes"] = len(fixed)

    # dedupe exact duplicate pairs (keep first)
    seen, dedup = set(), []
    for r in nso_rows:
        key = (r["old_ward_code"], r["new_ward_code"])
        if key in seen:
            issues.append({"kind": "nso_duplicate_pair", "xlsx_row": r["xlsx_row"], "pair": key})
            continue
        seen.add(key)
        dedup.append(r)
    nso_rows = dedup

    # --- every registry ward must be covered, and nothing outside the registry used
    nso_old_codes = {r["old_ward_code"] for r in nso_rows}
    missing = sorted(set(wards_old) - nso_old_codes)
    extra = sorted(nso_old_codes - set(wards_old))
    stats["old_wards_registry"] = len(wards_old)
    stats["old_wards_missing_from_nso"] = missing
    assert not extra, extra

    # --- pairs the NSO table lacks but the resolution states (hand-checked, see RESOLUTION_ADDED_PAIRS)
    nso_pair_set = {(r["old_ward_code"], r["new_ward_code"]) for r in nso_rows}
    template = {r["new_ward_code"]: r for r in nso_rows}
    for (oc, nc), (ref, note) in sorted(RESOLUTION_ADDED_PAIRS.items()):
        assert (oc, nc) not in nso_pair_set, f"NSO now has {(oc, nc)}; drop it from RESOLUTION_ADDED_PAIRS"
        t, ow = template[nc], wards_old[oc]
        nso_rows.append({
            "xlsx_row": None, "origin": "resolution",
            "new_province_code": t["new_province_code"], "new_province_name": t["new_province_name"],
            "new_ward_name": t["new_ward_name"], "new_ward_code": nc,
            "old_ward_name": ow["name"], "old_ward_code": oc,
            "note": f"Nhập một phần (bổ sung theo NQ {ref}; thiếu trong bảng NSO)",
            "old_district_code": ow["district_code"], "old_district_name": districts_old[ow["district_code"]]["name"],
            "old_province_code": ow["province_code"],
        })
        issues.append({"kind": "pair_added_from_resolution", "old_ward_code": oc, "old_ward_name": ow["name"],
                       "new_ward_code": nc, "new_ward_name": t["new_ward_name"], "resolution": ref, "evidence": note})
    stats["pairs_added_from_resolution"] = len(RESOLUTION_ADDED_PAIRS)

    # --- new provinces ---------------------------------------------------------
    old_to_new_prov = {}
    for new_code, (_, parts, _) in NQ202.items():
        for p in parts:
            old_to_new_prov[p] = new_code
    assert sorted(old_to_new_prov) == sorted(provinces_old), "NQ202 table must cover 63 old provinces"
    # derive merged_from from the NSO table and compare with the resolution
    derived = collections.defaultdict(set)
    for r in nso_rows:
        derived[r["new_province_code"]].add(wards_old[r["old_ward_code"]]["province_code"])
    for new_code, (_, parts, _) in NQ202.items():
        if derived[new_code] != set(parts):
            raise SystemExit(f"NSO-derived merged_from for {new_code} = {derived[new_code]} != NQ202 {parts}")
    assert len(derived) == 34
    nso_prov_names = {r["new_province_code"]: r["new_province_name"] for r in nso_rows}
    provinces_new = []
    for new_code in sorted(NQ202):
        name, parts, seat = NQ202[new_code]
        if name_key(nso_prov_names[new_code]) != name_key(name):
            issues.append({"kind": "province_name_mismatch", "code": new_code,
                           "nq202": name, "nso": nso_prov_names[new_code]})
        ptype, pshort = split_province(name)
        provinces_new.append({
            "code": new_code,
            "name": name,
            "short_name": pshort,
            "type": ptype,
            "merged_from": sorted(parts),
            "capital": None,
            "seat_old_province_code": seat,
        })

    # --- new wards ---------------------------------------------------------------
    cas_by_code, vnau_new, va_by_code = load_new_wards_checks()
    new_wards: dict[str, dict] = {}
    for r in nso_rows + no_old:
        c = r["new_ward_code"]
        cas = cas_by_code.get(c)
        if cas is not None and name_key(cas["name"]) != name_key(r["new_ward_name"]):
            # NSO typo (e.g. "Xa Ea Kly"): fall back to the cas.so official list
            issues.append({"kind": "nso_new_ward_name_typo_fixed", "code": c, "nso": r["new_ward_name"],
                           "fixed": nfc(cas["name"])})
            r["new_ward_name"] = nfc(cas["name"])
        if c in new_wards:
            if name_key(new_wards[c]["name"]) != name_key(r["new_ward_name"]):
                issues.append({"kind": "nso_new_ward_name_inconsistent", "code": c,
                               "names": [new_wards[c]["name"], r["new_ward_name"]]})
            continue
        wtype, wshort = split_ward(r["new_ward_name"])
        new_wards[c] = {
            "code": c,
            "name": r["new_ward_name"],
            "short_name": wshort,
            "type": wtype,
            "province_code": r["new_province_code"],
        }
    # verify new wards against cas.so (official codes + resolution no.), vietnamadminunits, vietaddr
    spelling_variants = 0
    for c, w in new_wards.items():
        cas = cas_by_code.get(c)
        w["resolution"] = None
        if cas is None:
            issues.append({"kind": "new_ward_not_in_cas", "code": c, "name": w["name"]})
        else:
            m = re.search(r"(\d+/NQ-UBTVQH15)", cas.get("decree") or "")
            w["resolution"] = m.group(1) if m else None
            if name_key(cas["name"]) != name_key(w["name"]):
                issues.append({"kind": "new_ward_name_mismatch", "source": "cas.so", "code": c,
                               "nso": w["name"], "other": nfc(cas["name"])})
            if code2(cas["provinceCode"]) != w["province_code"]:
                issues.append({"kind": "new_ward_province_mismatch", "source": "cas.so", "code": c})
        for src, other in (("vietnamadminunits", vnau_new.get(c)), ("vietaddr", va_by_code.get(c))):
            if other is None:
                issues.append({"kind": "new_ward_missing", "source": src, "code": c, "name": w["name"]})
                continue
            oname = nfc(other.get("ward") or other.get("name"))
            if name_key(oname) != name_key(w["name"]):
                issues.append({"kind": "new_ward_name_mismatch", "source": src, "code": c,
                               "nso": w["name"], "other": oname})
            elif oname != w["name"]:
                spelling_variants += 1
    stats["new_ward_spelling_variants_vs_other_lists"] = spelling_variants
    stats["new_wards"] = len(new_wards)
    stats["new_wards_by_type"] = dict(collections.Counter(w["type"] for w in new_wards.values()))

    # --- canonical old ward names: the resolution decides when registry and NSO disagree ----------
    old_alt, name_decisions, not_found = canonicalise_old_names(wards_old, nso_rows, new_wards, issues)
    stats["old_ward_name_decisions"] = name_decisions
    stats["old_wards_with_alt_name"] = len(old_alt)
    stats["old_wards_name_not_in_resolution_clause"] = not_found

    # --- structural change classification (from the NSO backbone) ----------------
    targets = collections.defaultdict(set)   # old -> {new}
    sources = collections.defaultdict(set)   # new -> {old}
    for r in nso_rows:
        targets[r["old_ward_code"]].add(r["new_ward_code"])
        sources[r["new_ward_code"]].add(r["old_ward_code"])

    # --- lineage B and derivatives ----------------------------------------------
    vnau_rows = load_vnau()
    vnau_pairs = set()
    vnau_targets = collections.defaultdict(set)
    vnau_name_mismatch = 0
    vnau_by_names: dict[tuple, tuple] = {}
    for r in vnau_rows:
        oc, nc = code5(r["wardCode"]), code5(r["newWardCode"])
        if not oc:
            continue
        rc, status = idx.resolve(oc, r["ward"], code3(r["districtCode"]))
        if status not in ("ok", "spelling"):
            issues.append({"kind": "vnau_old_code_name_mismatch", "vnau_code": oc, "vnau_name": r["ward"],
                           "registry_name": idx.wards[oc]["name"] if oc in idx.wards else None,
                           "resolved": rc, "status": status})
            vnau_name_mismatch += 1
        if rc is None:
            continue
        oc = rc
        vnau_by_names[(nfc(r["province"]), nfc(r["district"]), nfc(r["ward"]), nfc(r["newWard"]))] = (oc, nc)
        vnau_pairs.add((oc, nc))
        vnau_targets[oc].add(nc)
    stats["vnau_old_code_name_mismatch"] = vnau_name_mismatch

    # undertheseanlp (copy of vnau 1.0.4): no codes -> match by names
    uts = load_uts()
    dist_by_name = collections.defaultdict(list)
    for d in districts_old.values():
        dist_by_name[(d["province_code"], loose_key(d["name"]))].append(d["code"])
    new_by_names = collections.defaultdict(list)
    for w in new_wards.values():
        new_by_names[(w["province_code"], loose_key(w["name"]))].append(w["code"])
    uts_prov_code = {k: code2(v["code"]) for k, v in uts["province_names"].items()}
    uts_oldprov_code = {k: code2(v["code"]) for k, v in uts["old_province_names"].items()}
    uts_pairs, uts_unmatched = set(), []
    for rec in uts["ward_mapping"]:
        hit = vnau_by_names.get((nfc(rec["old_province"]), nfc(rec["old_district"]), nfc(rec["old_ward"]),
                                 nfc(rec["new_ward"])))
        if hit is not None:
            uts_pairs.add(hit)
            continue
        dc = dist_by_name.get((uts_oldprov_code.get(rec["old_province_key"], ""), loose_key(rec["old_district"])), [])
        oc = idx.resolve("", rec["old_ward"], dc[0])[0] if len(dc) == 1 and rec["old_ward"] else None
        nk = new_by_names.get((uts_prov_code.get(rec["new_province_key"], ""), loose_key(rec["new_ward"])), [])
        if oc is None or len(nk) != 1:
            uts_unmatched.append(rec)
            continue
        uts_pairs.add((oc, nk[0]))
    stats["uts_records"] = len(uts["ward_mapping"])
    stats["uts_records_unmatched_by_name"] = len(uts_unmatched)
    for rec in uts_unmatched:
        issues.append(dict(kind="uts_record_unmatched", **rec))

    vietaddr_pairs = load_vietaddr()
    bando = load_bando()

    # --- ward_mapping -----------------------------------------------------------
    mapping = []
    note_partial = re.compile(r"m[ộo]t\s+ph[ầa]n", re.I)
    partial_note_mismatch = []
    for r in sorted(nso_rows, key=lambda x: (x["old_ward_code"], x["new_ward_code"])):
        oc, nc = r["old_ward_code"], r["new_ward_code"]
        ow, nw = wards_old[oc], new_wards[nc]
        od = districts_old[ow["district_code"]]
        op = provinces_old[ow["province_code"]]
        np_code = nw["province_code"]
        assert old_to_new_prov[op["code"]] == np_code, (r, op, np_code)
        npv = next(p for p in provinces_new if p["code"] == np_code)

        n_t, n_s = len(targets[oc]), len(sources[nc])
        if n_t > 1:
            change_type = "divided"
        elif n_s > 1:
            change_type = "merged"
        elif name_key(ow["name"]) == name_key(nw["name"]):
            change_type = "unchanged"
        elif r["note"].lower().startswith("giữ nguyên") and ow["type"] == nw["type"]:
            # NSO: officially kept as-is; the two registries only spell the name differently
            change_type = "unchanged"
        else:
            change_type = "renamed"
        spelling_variant = change_type == "unchanged" and name_key(ow["name"]) != name_key(nw["name"])
        is_partial = n_t > 1
        if bool(note_partial.search(r["note"])) != is_partial:
            partial_note_mismatch.append({"old": oc, "old_name": ow["name"], "new": nc,
                                          "new_name": nw["name"], "note": r["note"], "n_targets": n_t})

        from_res = r.get("origin") == "resolution"
        srcs = [SRC_RES] if from_res else [SRC_NSO]
        if not from_res and (oc, nc) in RESOLUTION_VERIFIED_PAIRS:
            srcs.append(SRC_RES)
        if (oc, nc) in vnau_pairs:
            srcs.append(SRC_VNAU)
        if (oc, nc) in uts_pairs:
            srcs.append(SRC_UTS)
        if (oc, nc) in vietaddr_pairs:
            srcs.append(SRC_VIETADDR)
        # independent attestations: A = nso, B = vietnamadminunits, R = resolution text (hand-checked)
        if sum(x in srcs for x in (SRC_NSO, SRC_VNAU, SRC_RES)) >= 2:
            confidence = "high"
        elif SRC_NSO in srcs and oc in vnau_targets:
            confidence = "conflict"
        else:
            confidence = "single"

        # bando composition text: does it name this old ward? (adjudication aid only)
        btxt = bando.get((name_key(npv["short_name"]), name_key(nw["name"])))
        bando_mentions = None
        if btxt is not None:
            # compare item by item on a key without spaces/hyphens ("Xã EaBar" ~ "Xã Ea Bar",
            # "Văn Miếu - Quốc Tử Giám" ~ "Văn Miếu Quốc Tử Giám"); try both spellings of the old ward
            # (bando also writes bare names "Rạch Ông" and sometimes another unit type: compare the
            # name without its type prefix too). "Không sáp nhập" = bando says the ward is kept 1:1.
            if name_key(btxt).startswith(name_key("Không sáp nhập")):
                bando_mentions = n_s == 1 and n_t == 1
            else:
                segs = {squash_key(x) for x in re.split(r"[,;()]", btxt)}
                segs |= {re.sub(r"^(?:và)?(?:xã|phường|thịtrấn)", "", sg) for sg in segs}
                names = [ow["name"]] + ([old_alt[oc]] if oc in old_alt else [])
                keys = {squash_key(x) for x in names} | {squash_key(short(x)) for x in names}
                bando_mentions = any(sg == k or sg.endswith(k) and not k.isdigit() for sg in segs for k in keys)
        province_name_changed = name_key(op["name"]) != name_key(npv["name"])
        name_changed = name_key(ow["name"]) != name_key(nw["name"])

        mapping.append({
            "old_ward_code": oc,
            "old_ward_name": ow["name"],
            "old_ward_type": ow["type"],
            "old_district_code": od["code"],
            "old_district_name": od["name"],
            "old_province_code": op["code"],
            "old_province_name": op["name"],
            "new_ward_code": nc,
            "new_ward_name": nw["name"],
            "new_ward_type": nw["type"],
            "new_province_code": np_code,
            "new_province_name": npv["name"],
            "change_type": change_type,
            "province_changed": len(npv["merged_from"]) > 1,
            "ward_changed": change_type != "unchanged",
            "is_partial": is_partial,
            "sources": srcs,
            "confidence": confidence,
            # --- extensions (documented in SPEC.md) ---
            "name_changed": name_changed,
            "province_name_changed": province_name_changed,
            "surface_answer_changed": name_changed or province_name_changed,
            "spelling_variant": spelling_variant,
            "target_set_agrees": vnau_targets.get(oc) == targets[oc],
            "n_old_sources": n_s,
            "n_new_targets": n_t,
            "nso_note": r["note"],
            # the other registry's spelling of the old ward (non-canonical; alias for scoring)
            "old_ward_name_alt": old_alt.get(oc),
            "bando_mentions_old_ward": bando_mentions,
            "resolution": nw.get("resolution"),
        })

    # --- cross-source disagreement inventory -----------------------------------
    nso_pairs = {(m["old_ward_code"], m["new_ward_code"]) for m in mapping if SRC_NSO in m["sources"]}
    mapped_pairs = {(m["old_ward_code"], m["new_ward_code"]) for m in mapping}
    for oc, nc in sorted(vnau_pairs - mapped_pairs):
        ow = wards_old.get(oc)
        nw = new_wards.get(nc)
        issues.append({"kind": "pair_only_in_vietnamadminunits", "old_ward_code": oc,
                       "old_ward_name": ow and ow["name"], "old_district": ow and districts_old[ow["district_code"]]["name"],
                       "new_ward_code": nc, "new_ward_name": nw and nw["name"],
                       "nso_targets": sorted(targets.get(oc, [])),
                       "nso_target_names": [new_wards[x]["name"] for x in sorted(targets.get(oc, []))]})
    for m in mapping:
        if SRC_VNAU not in m["sources"]:
            issues.append({"kind": f"pair_not_in_vietnamadminunits_{m['confidence']}", "sources": m["sources"], "old_ward_code": m["old_ward_code"],
                           "old_ward_name": m["old_ward_name"], "old_district": m["old_district_name"],
                           "new_ward_code": m["new_ward_code"], "new_ward_name": m["new_ward_name"],
                           "nso_note": m["nso_note"], "vnau_targets": sorted(vnau_targets.get(m["old_ward_code"], [])),
                           "bando_mentions_old_ward": m["bando_mentions_old_ward"]})
    for oc, nc in sorted(vietaddr_pairs - nso_pairs):
        issues.append({"kind": "pair_only_in_vietaddr", "old_ward_code": oc, "new_ward_code": nc})
    for p in partial_note_mismatch:
        issues.append(dict(kind="partial_flag_vs_nso_note", **p))

    # per-old-ward agreement (target sets), new province agreement
    per_ward = collections.Counter()
    for oc in targets:
        a, b = targets[oc], vnau_targets.get(oc)
        if b is None:
            per_ward["missing_in_vnau"] += 1
        elif a == b:
            per_ward["identical_target_set"] += 1
        elif a < b:
            per_ward["vnau_superset"] += 1
        elif b < a:
            per_ward["vnau_subset"] += 1
        elif a & b:
            per_ward["overlap_differs"] += 1
        else:
            per_ward["disjoint"] += 1
    stats["per_old_ward_vs_vnau"] = dict(per_ward)
    prov_dis = 0
    for oc, nc in vnau_pairs:
        if oc in wards_old and nc in new_wards:
            if new_wards[nc]["province_code"] != old_to_new_prov[wards_old[oc]["province_code"]]:
                prov_dis += 1
    stats["vnau_pairs_new_province_disagreement"] = prov_dis
    stats["pairs"] = {
        "nso": len(nso_pairs), "vnau": len(vnau_pairs), "uts": len(uts_pairs), "vietaddr": len(vietaddr_pairs),
        "nso&vnau": len(nso_pairs & vnau_pairs), "nso&uts": len(nso_pairs & uts_pairs),
        "nso&vietaddr": len(nso_pairs & vietaddr_pairs), "vnau&uts": len(vnau_pairs & uts_pairs),
        "only_vnau": len(vnau_pairs - mapped_pairs), "only_vietaddr": len(vietaddr_pairs - mapped_pairs),
        "mapping": len(mapped_pairs), "mapping_not_nso": len(mapped_pairs - nso_pairs),
        "nso_not_vietaddr": len(nso_pairs - vietaddr_pairs),
    }
    stats["mapping_rows"] = len(mapping)
    stats["change_type"] = dict(collections.Counter(m["change_type"] for m in mapping))
    stats["confidence"] = dict(collections.Counter(m["confidence"] for m in mapping))
    stats["is_partial_rows"] = sum(m["is_partial"] for m in mapping)
    stats["partial_flag_vs_nso_note_mismatch"] = len(partial_note_mismatch)
    stats["bando_mentions"] = dict(collections.Counter(str(m["bando_mentions_old_ward"]) for m in mapping))
    cell = collections.Counter((m["province_changed"], m["ward_changed"]) for m in mapping)
    stats["cells_rows"] = {f"province_changed={a},ward_changed={b}": n for (a, b), n in sorted(cell.items())}
    # per old ward (each old ward counted once; divided wards are ward_changed=True on all rows)
    ow_cell = collections.Counter()
    ow_type = {}
    for m in mapping:
        ow_type[m["old_ward_code"]] = (m["province_changed"], m["ward_changed"], m["change_type"])
    for pc, wc, _ in ow_type.values():
        ow_cell[(pc, wc)] += 1
    stats["cells_old_wards"] = {f"province_changed={a},ward_changed={b}": n for (a, b), n in sorted(ow_cell.items())}
    stats["change_type_old_wards"] = dict(collections.Counter(t for _, _, t in ow_type.values()))
    ct_cell = collections.Counter((m["change_type"], m["province_changed"]) for m in mapping)
    stats["change_type_x_province_changed_rows"] = {f"{a},province_changed={b}": n for (a, b), n in sorted(ct_cell.items())}
    stats["name_changed_rows"] = sum(m["name_changed"] for m in mapping)
    stats["province_name_changed_rows"] = sum(m["province_name_changed"] for m in mapping)
    sc = collections.Counter((m["province_changed"], m["ward_changed"], m["surface_answer_changed"]) for m in mapping)
    stats["cells_rows_by_surface_answer_changed"] = {
        f"province_changed={a},ward_changed={b},surface_answer_changed={c}": n for (a, b, c), n in sorted(sc.items())}
    stats["merged_but_same_name_rows"] = sum(1 for m in mapping if m["change_type"] == "merged" and not m["name_changed"])
    stats["new_wards_without_old_ward"] = sorted(set(new_wards) - set(sources))
    stats["issues_by_kind"] = dict(collections.Counter(i["kind"] for i in issues))

    # --- write -------------------------------------------------------------------
    used_districts = {w["district_code"] for w in wards_old.values()}
    write_jsonl(OUT / "provinces_old.jsonl", [
        {"code": p["code"], "name": p["name"], "short_name": p["short_name"], "type": p["type"]}
        for p in sorted(provinces_old.values(), key=lambda x: x["code"])])
    write_jsonl(OUT / "provinces_new.jsonl", provinces_new)
    write_jsonl(OUT / "districts_old.jsonl", [
        dict(d, has_wards=d["code"] in used_districts) for d in sorted(districts_old.values(), key=lambda x: x["code"])])
    write_jsonl(OUT / "wards_old.jsonl", [
        dict({k: w[k] for k in ("code", "name", "short_name", "type", "district_code", "province_code")},
             name_alt=old_alt.get(w["code"]))
        for w in sorted(wards_old.values(), key=lambda x: x["code"])])
    write_jsonl(OUT / "wards_new.jsonl", [
        {k: w[k] for k in ("code", "name", "short_name", "type", "province_code", "resolution")}
        for w in sorted(new_wards.values(), key=lambda x: x["code"])])
    write_jsonl(OUT / "ward_mapping.jsonl", mapping)
    write_jsonl(OUT / "crosscheck_issues.jsonl", issues)
    (OUT / "build_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in stats.items() if k not in ("nso_rows_without_old_ward",)},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
