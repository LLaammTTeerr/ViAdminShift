"""Shared loaders and helpers for the benchmark generator.

Everything here is pure data handling: the canonical tables in ``data/processed`` (read
only), coordinates from the vietnamadminunits CSVs (parsed as data, used ONLY to rank
plausible distractors by distance, never for a gold label), and Vietnamese name formatting.
"""

from __future__ import annotations

import csv
import json
import math
import random
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from viadmin.data.normalize import name_key
from viadmin.eval.normalize import normalize_name, strip_diacritics

SEED = 13
ROOT = Path(__file__).resolve().parents[3]
PROCESSED = ROOT / "data" / "processed"
WIKI = ROOT / "data" / "wiki"
BENCH = ROOT / "data" / "benchmark"
VAU = ROOT / "data" / "raw" / "vietnamadminunits" / "data" / "processed"


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def rng_for(key: str) -> random.Random:
    """Per-key deterministic RNG (string seeds are stable across Python runs)."""
    return random.Random(f"{SEED}:{key}")


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n")


# ----------------------------------------------------------------------------- names

_PREFIXES = ("Thành phố", "Thị trấn", "Thị xã", "Đặc khu", "Phường", "Huyện", "Quận", "Tỉnh", "Xã", "Thủ đô")


def lower_prefix(full: str) -> str:
    """'Xã Đại Hợp' -> 'xã Đại Hợp'; 'Thành phố Hồ Chí Minh' -> 'thành phố Hồ Chí Minh'."""
    for p in _PREFIXES:
        if full.lower().startswith(p.lower() + " "):  # registry quirk: "Thị Xã Mường Lay"
            return p.lower() + full[len(p):]
    return full


def lc_first(s: str) -> str:
    """Lower-case the first character (used after a cue prefix). Only called on
    questions that start with a common word or a unit prefix, never a proper noun."""
    return s[:1].lower() + s[1:]


def short_of(full: str) -> str:
    for p in _PREFIXES:
        if full.lower().startswith(p.lower() + " "):
            return full[len(p) + 1:]
    return full


def key(s: str) -> str:
    """Tone-placement/case-insensitive comparison key of a bare name (same as viadmin.data.normalize.name_key)."""
    return name_key(s)


def norm_choice(s: str) -> str:
    return normalize_name(s)


def nodiac(s: str) -> str:
    return strip_diacritics(s)


# ----------------------------------------------------------------------------- geo

def _haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def _fcode(x: str, width: int) -> str | None:
    x = (x or "").strip()
    if not x:
        return None
    try:
        return str(int(float(x))).zfill(width)
    except ValueError:
        return None


def _flt(x: str) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# ----------------------------------------------------------------------------- tables

@dataclass
class Tables:
    provinces_old: list[dict]
    provinces_new: list[dict]
    districts_old: list[dict]
    wards_old: list[dict]
    wards_new: list[dict]
    mapping: list[dict]
    old_ward_xy: dict[str, tuple[float, float]] = field(default_factory=dict)
    new_ward_xy: dict[str, tuple[float, float]] = field(default_factory=dict)
    old_prov_xy: dict[str, tuple[float, float]] = field(default_factory=dict)
    new_prov_xy: dict[str, tuple[float, float]] = field(default_factory=dict)

    # ---- indexes
    @cached_property
    def pold(self) -> dict[str, dict]:
        return {p["code"]: p for p in self.provinces_old}

    @cached_property
    def pnew(self) -> dict[str, dict]:
        return {p["code"]: p for p in self.provinces_new}

    @cached_property
    def dold(self) -> dict[str, dict]:
        return {d["code"]: d for d in self.districts_old}

    @cached_property
    def wold(self) -> dict[str, dict]:
        return {w["code"]: w for w in self.wards_old}

    @cached_property
    def wnew(self) -> dict[str, dict]:
        return {w["code"]: w for w in self.wards_new}

    @cached_property
    def rows_by_old(self) -> dict[str, list[dict]]:
        d: dict[str, list[dict]] = defaultdict(list)
        for r in self.mapping:
            d[r["old_ward_code"]].append(r)
        return dict(d)

    @cached_property
    def rows_by_new(self) -> dict[str, list[dict]]:
        d: dict[str, list[dict]] = defaultdict(list)
        for r in self.mapping:
            d[r["new_ward_code"]].append(r)
        return dict(d)

    @cached_property
    def new_of_old_prov(self) -> dict[str, str]:
        return {o: p["code"] for p in self.provinces_new for o in p["merged_from"]}

    @cached_property
    def new_ward_keys_by_prov(self) -> dict[str, dict[str, list[str]]]:
        """new province code -> short-name key -> [new ward codes]."""
        d: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        for w in self.wards_new:
            d[w["province_code"]][key(w["short_name"])].append(w["code"])
        return d

    @cached_property
    def new_ward_key_count(self) -> dict[str, int]:
        c: dict[str, int] = defaultdict(int)
        for w in self.wards_new:
            c[key(w["short_name"])] += 1
        return c

    @cached_property
    def old_ward_keys(self) -> dict[str, list[dict]]:
        """short-name key (canonical and alt spelling) -> old ward rows."""
        d: dict[str, list[dict]] = defaultdict(list)
        for w in self.wards_old:
            d[key(w["short_name"])].append(w)
            if w.get("name_alt"):
                k2 = key(short_of(w["name_alt"]))
                if k2 != key(w["short_name"]):
                    d[k2].append(w)
        return d

    @cached_property
    def old_district_keys(self) -> dict[str, list[dict]]:
        d: dict[str, list[dict]] = defaultdict(list)
        for x in self.districts_old:
            d[key(x["short_name"])].append(x)
        return d

    @cached_property
    def wards_old_by_district(self) -> dict[str, list[dict]]:
        d: dict[str, list[dict]] = defaultdict(list)
        for w in self.wards_old:
            d[w["district_code"]].append(w)
        return d

    @cached_property
    def districts_by_prov(self) -> dict[str, list[dict]]:
        d: dict[str, list[dict]] = defaultdict(list)
        for x in self.districts_old:
            d[x["province_code"]].append(x)
        return d

    # ---- geography (distractor ranking only)
    def xy_old_ward(self, code: str) -> tuple[float, float]:
        if code in self.old_ward_xy:
            return self.old_ward_xy[code]
        return self.old_prov_xy[self.wold[code]["province_code"]]

    def xy_new_ward(self, code: str) -> tuple[float, float]:
        if code in self.new_ward_xy:
            return self.new_ward_xy[code]
        return self.new_prov_xy[self.wnew[code]["province_code"]]

    def nearest_new_provinces(self, xy: tuple[float, float], exclude: set[str]) -> list[str]:
        cands = [(round(_haversine(xy, v), 3), c) for c, v in self.new_prov_xy.items() if c not in exclude]
        return [c for _, c in sorted(cands)]

    def nearest_old_provinces(self, xy: tuple[float, float], exclude: set[str]) -> list[str]:
        cands = [(round(_haversine(xy, v), 3), c) for c, v in self.old_prov_xy.items() if c not in exclude]
        return [c for _, c in sorted(cands)]

    def nearest_new_wards(self, code: str, same_prov: bool = True) -> list[str]:
        xy = self.xy_new_ward(code)
        prov = self.wnew[code]["province_code"]
        cands = [(round(_haversine(xy, self.xy_new_ward(w["code"])), 4), w["code"])
                 for w in self.wards_new
                 if w["code"] != code and (not same_prov or w["province_code"] == prov)]
        return [c for _, c in sorted(cands)]


def _load_coords(t: Tables) -> None:
    legacy = VAU / "legacy_63-province-10040-ward_with_location.csv"
    new = VAU / "2025_34-province-3221-ward_with_location.csv"
    pxy: dict[str, list[tuple[float, float]]] = defaultdict(list)
    with open(legacy, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            wc, pc = _fcode(r.get("wardCode", ""), 5), _fcode(r.get("provinceCode", ""), 2)
            lat, lon = _flt(r.get("wardLat")), _flt(r.get("wardLon"))
            plat, plon = _flt(r.get("provinceLat")), _flt(r.get("provinceLon"))
            if wc and lat is not None and lon is not None:
                t.old_ward_xy[wc] = (lat, lon)
            if pc and plat is not None and plon is not None:
                pxy[pc].append((plat, plon))
    for pc, v in pxy.items():
        t.old_prov_xy[pc] = v[0]
    nxy: dict[str, tuple[float, float]] = {}
    with open(new, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            wc, pc = _fcode(r.get("wardCode", ""), 5), _fcode(r.get("provinceCode", ""), 2)
            lat, lon = _flt(r.get("wardLat")), _flt(r.get("wardLon"))
            plat, plon = _flt(r.get("provinceLat")), _flt(r.get("provinceLon"))
            if wc and lat is not None and lon is not None:
                t.new_ward_xy[wc] = (lat, lon)
            if pc and plat is not None and plon is not None:
                nxy.setdefault(pc, (plat, plon))
    t.new_prov_xy.update(nxy)
    # fall back to the mean of ward coordinates for any province without a centroid
    for p in t.provinces_old:
        if p["code"] not in t.old_prov_xy:
            pts = [t.old_ward_xy[w["code"]] for w in t.wards_old if w["province_code"] == p["code"] and w["code"] in t.old_ward_xy]
            t.old_prov_xy[p["code"]] = (sum(a for a, _ in pts) / len(pts), sum(b for _, b in pts) / len(pts))
    for p in t.provinces_new:
        if p["code"] not in t.new_prov_xy:
            pts = [t.new_ward_xy[w["code"]] for w in t.wards_new if w["province_code"] == p["code"] and w["code"] in t.new_ward_xy]
            t.new_prov_xy[p["code"]] = (sum(a for a, _ in pts) / len(pts), sum(b for _, b in pts) / len(pts))


def load_tables() -> Tables:
    t = Tables(
        provinces_old=load_jsonl(PROCESSED / "provinces_old.jsonl"),
        provinces_new=load_jsonl(PROCESSED / "provinces_new.jsonl"),
        districts_old=load_jsonl(PROCESSED / "districts_old.jsonl"),
        wards_old=load_jsonl(PROCESSED / "wards_old.jsonl"),
        wards_new=load_jsonl(PROCESSED / "wards_new.jsonl"),
        mapping=load_jsonl(PROCESSED / "ward_mapping.jsonl"),
    )
    _load_coords(t)
    return t
