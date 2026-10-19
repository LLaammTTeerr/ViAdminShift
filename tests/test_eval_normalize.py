import unicodedata

import pytest

from viadmin.eval.normalize import (
    canon_tone_placement,
    nodiac_keys,
    normalize_name,
    normalize_name_nodiac,
    normalize_text,
    strip_diacritics,
)


def nfd(s):
    return unicodedata.normalize("NFD", s)


@pytest.mark.parametrize(
    "a,b",
    [
        ("Thành phố Hồ Chí Minh", "Hồ Chí Minh"),
        ("TP. Hồ Chí Minh", "hồ chí minh"),
        ("TP.Hồ Chí Minh", "Hồ Chí Minh"),
        ("tp Hồ Chí Minh", "Hồ Chí Minh"),
        ("Tỉnh Bình Dương", "Bình Dương"),
        ("Phường Bến Nghé", "bến nghé"),
        ("Xã Tân Thạnh", "Tân Thạnh"),
        ("Thị trấn Củ Chi", "Củ Chi"),
        ("Thị xã Sơn Tây", "Sơn Tây"),
        ("Đặc khu Phú Quốc", "Phú Quốc"),
        ("Quận 1", "1"),
        ("Phường 01", "Phường 1"),
        ("  Bà Rịa  -  Vũng Tàu ", "Bà Rịa Vũng Tàu"),
        ("Văn Miếu – Quốc Tử Giám", "văn miếu quốc tử giám"),
        # tone placement
        ("Hoà Bình", "Hòa Bình"),
        ("Khánh Hoà", "Khánh Hòa"),
        ("Thuỷ Nguyên", "Thủy Nguyên"),
        ("Quý Lộc", "Qúy Lộc"),
        ("khoẻ", "khỏe"),
        # NFD input
        (nfd("Phường Bến Nghé"), "Bến Nghé"),
        ("BÌNH DƯƠNG", "bình dương"),
    ],
)
def test_equal_after_normalisation(a, b):
    assert normalize_name(a) == normalize_name(b)


@pytest.mark.parametrize(
    "a,b",
    [
        ("Phường Thành Công", "Công"),  # "thành" alone is not a prefix
        ("Hòa Bình", "Hòa Bính"),
        ("An Phú", "Tân An Phú"),
        ("Phường 1", "Phường 11"),
        ("Thuận An", "Thuận Hòa"),
    ],
)
def test_not_equal(a, b):
    assert normalize_name(a) != normalize_name(b)


def test_prefix_stripped_only_once_and_never_empty():
    assert normalize_name("Phường Thành Công") == "thành công"
    assert normalize_name("Xã") == "xã"
    assert normalize_name("Thành phố") == "thành phố"
    assert normalize_name("Thị xã Xã Đàn") == "xã đàn"  # only one prefix removed


def test_longest_prefix_first():
    assert normalize_name("Thị xã Bến Cát") == "bến cát"  # not "thị bến cát"... nor "xã bến cát"
    assert normalize_name("Thành phố Thủ Đức") == "thủ đức"


def test_tone_canon_is_idempotent_and_leaves_other_words():
    s = normalize_text("Hoàng Mai Nguyễn Quyền")
    assert canon_tone_placement(s) == s
    assert "nguyễn" in s and "quyền" in s


def test_strip_diacritics_dd():
    assert strip_diacritics("Đắk Lắk") == "Dak Lak"
    assert strip_diacritics("đường Điện Biên Phủ") == "duong Dien Bien Phu"
    assert strip_diacritics(nfd("Hồ Chí Minh")) == "Ho Chi Minh"


def test_nodiac():
    assert normalize_name_nodiac("Phường Bến Nghé") == "ben nghe"
    assert normalize_name_nodiac("Phuong Ben Nghe") == "ben nghe"
    assert normalize_name_nodiac("Xã Xà Phìn") == "xa phin"  # not "phin"
    assert normalize_name_nodiac("Hoà Bình") == normalize_name_nodiac("Hòa Bình") == "hoa binh"
    # diacritic-free input that starts with a prefix-looking word keeps an alternative key
    assert "quan lan" in nodiac_keys("Quan Lan")
    assert "quan lan" in nodiac_keys("Xã Quan Lạn")


def test_empty():
    assert normalize_name(None) == ""
    assert normalize_name("") == ""
    assert normalize_name("  ...  ") == ""
