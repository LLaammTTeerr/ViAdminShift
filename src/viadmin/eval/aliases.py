"""Alias tables used by the scorer.

All keys/values are written in *surface* form and normalised at import time with
:func:`viadmin.eval.normalize.normalize_name`, so they may contain prefixes,
punctuation or old-style tone marks.

Aliases are applied to the GOLD side only (answer + answer_aliases are expanded
into an accept-set; the prediction is never expanded). This prevents e.g. a
ward-level answer "Sài Gòn" from being treated as TP.HCM.

Three tables:

* ``EQUIVALENT``: groups of names that denote the *same current* entity under the
  same name. A prediction hitting any member counts as ``correct``.
* ``LEGACY``: current name -> names this entity had *before* a rename. A prediction
  hitting a legacy name of the gold is labelled ``outdated`` (match_detail
  ``legacy_name``). Example: Thừa Thiên Huế became the centrally-run city Huế on
  1/1/2025 (Nghị quyết 175/2024/QH15, effective 01/01/2025), so "Thừa Thiên Huế" is an
  outdated name for "Huế" even though it predates the 1/7/2025 reform.
* ``SOFT``: colloquial names that are deliberately NOT accepted as correct but are
  tracked (match_detail ``soft_alias``) so a lenient re-scoring is possible.
  "Sài Gòn" for TP.HCM is here: since 1/7/2025 "phường Sài Gòn" is a real ward of
  TP.HCM (Nghị quyết 1685/NQ-UBTVQH15: Bến Nghé + parts of Đa Kao and Nguyễn Thái
  Bình), so "Sài Gòn" as an answer is ambiguous between a ward and the city.
"""

from __future__ import annotations

EQUIVALENT: list[list[str]] = [
    [
        "Thành phố Hồ Chí Minh",
        "TP.HCM",
        "TP HCM",
        "TPHCM",
        "TP. Hồ Chí Minh",
        "HCM",
        "HCMC",
        "Ho Chi Minh City",
        "Thành phố HCM",
    ],
    ["Hà Nội", "Thủ đô Hà Nội", "Hanoi"],
    ["Bà Rịa - Vũng Tàu", "Bà Rịa Vũng Tàu", "BR-VT", "BRVT"],
    ["Đắk Lắk", "Đăk Lăk", "Đắc Lắc", "Daklak", "Dak Lak"],
    ["Đắk Nông", "Đăk Nông", "Đắc Nông", "Daknong", "Dak Nong"],
    ["Kon Tum", "Kontum"],
    ["Bắc Kạn", "Bắc Cạn"],
    ["Đà Nẵng", "Danang"],
]

LEGACY: dict[str, list[str]] = {
    "Huế": ["Thừa Thiên Huế", "Thừa Thiên - Huế", "Thừa Thiên-Huế", "TT Huế", "TTH"],
}

SOFT: dict[str, list[str]] = {
    "Thành phố Hồ Chí Minh": ["Sài Gòn", "Saigon", "Sài Gòn - Gia Định"],
}

# Short names of the 63 pre-reform provinces (verified against
# data/processed/provinces_old.jsonl) plus the pre-2025 name of Huế.
# Many post-reform WARDS carry these names (e.g. "Phường Bình Dương", "Xã Hòa Bình",
# "Phường Bắc Giang"). For such ward golds the scorer requires the prediction to carry
# a ward-level prefix (phường/xã/thị trấn/đặc khu); a bare "Bình Dương" is ambiguous
# with the province and is NOT accepted (match_detail "ambiguous_province_name").
PROVINCE_NAMES: list[str] = [
    "An Giang", "Bà Rịa - Vũng Tàu", "Bình Dương", "Bình Phước", "Bình Thuận", "Bình Định",
    "Bạc Liêu", "Bắc Giang", "Bắc Kạn", "Bắc Ninh", "Bến Tre", "Cao Bằng", "Cà Mau", "Cần Thơ",
    "Gia Lai", "Huế", "Hà Giang", "Hà Nam", "Hà Nội", "Hà Tĩnh", "Hòa Bình", "Hưng Yên",
    "Hải Dương", "Hải Phòng", "Hậu Giang", "Hồ Chí Minh", "Khánh Hòa", "Kiên Giang", "Kon Tum",
    "Lai Châu", "Long An", "Lào Cai", "Lâm Đồng", "Lạng Sơn", "Nam Định", "Nghệ An", "Ninh Bình",
    "Ninh Thuận", "Phú Thọ", "Phú Yên", "Quảng Bình", "Quảng Nam", "Quảng Ngãi", "Quảng Ninh",
    "Quảng Trị", "Sóc Trăng", "Sơn La", "Thanh Hóa", "Thái Bình", "Thái Nguyên", "Tiền Giang",
    "Trà Vinh", "Tuyên Quang", "Tây Ninh", "Vĩnh Long", "Vĩnh Phúc", "Yên Bái", "Điện Biên",
    "Đà Nẵng", "Đắk Lắk", "Đắk Nông", "Đồng Nai", "Đồng Tháp", "Thừa Thiên Huế",
]
