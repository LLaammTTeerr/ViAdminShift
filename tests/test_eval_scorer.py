import pytest

from viadmin.eval.scorer import clean_output, extract_letter, score

CHOICES = ["Bình Dương", "Thành phố Hồ Chí Minh", "Đồng Nai", "Tây Ninh"]


def mcq(answer="B", old="A", choices=CHOICES):
    return {"id": "m1", "format": "mcq", "choices": list(choices), "answer": answer,
            "answer_aliases": [], "old_answer": old, "meta": {}}


def short(answer, aliases=(), old=None):
    return {"id": "s1", "format": "short", "choices": None, "answer": answer,
            "answer_aliases": list(aliases), "old_answer": old, "meta": {}}


# --------------------------------------------------------------- MCQ letter extraction

@pytest.mark.parametrize(
    "raw,letter",
    [
        ("B", "B"),
        (" B ", "B"),
        ("B.", "B"),
        ("(B)", "B"),
        ("[B]", "B"),
        ("**B**", "B"),
        ("b", "B"),
        ("B)", "B"),
        ("Đáp án: B", "B"),
        ("Đáp án đúng là B.", "B"),
        ("Đáp án: (B) Thành phố Hồ Chí Minh", "B"),
        ("Câu trả lời: C", "C"),
        ("Tôi chọn D vì...", "D"),
        ("Answer: A", "A"),
        ("The answer is C", "C"),
        ("B. Thành phố Hồ Chí Minh", "B"),
        ("B: TP.HCM", "B"),
        ("<think>\nhmm A or B\n</think>\n\nB", "B"),
        ("<think></think>C", "C"),
        ("C\n\nGiải thích: Tỉnh Bình Dương được sáp nhập vào Thành", "C"),
        ("B.\nVì Đáp án A sai", "B"),
        ("Thành phố Hồ Chí Minh", "B"),
        ("TP. Hồ Chí Minh", "B"),
        ("Đồng Nai.", "C"),
        ("Theo tôi đáp án hợp lý nhất là B.", "B"),
        ("Xã này thuộc phương án là C", "C"),
        ("Theo tôi thì là (D)", "D"),
        ("Tỉnh Tây Ninh", "D"),
        ("Theo tôi, xã này hiện thuộc Đồng Nai", "C"),
        ("Theo Nghị quyết năm 2025, tỉnh Bình Dương nhập vào Thành phố Hồ Chí Minh.\n\n**B**", "B"),
        ("Bình Dương cũ, nay là một phần của TP.HCM...\n\nB", "B"),
    ],
)
def test_extract_letter(raw, letter):
    got, how = extract_letter(raw, CHOICES)
    assert got == letter, how


@pytest.mark.parametrize(
    "raw",
    [
        "",
        None,
        "Tôi không biết.",
        "Cả A và B",
        "A, B",
        "Đáp án: A hoặc Đáp án: B",
        "<think>The answer is B",  # dangling think, nothing after
        "Đáp án là Bình Dương hoặc Đồng Nai",  # two choice texts
        "Có thể là Bình Dương hoặc Đồng Nai.\n\nKhông chắc chắn.",  # no letter on the last line
    ],
)
def test_extract_letter_invalid(raw):
    got, _ = extract_letter(raw, CHOICES)
    assert got is None


def test_dap_an_does_not_become_letter_d():
    # "Đáp án" must never yield "D" (diacritics are not stripped before extraction)
    got, _ = extract_letter("Đáp án nằm ở phương án thứ hai", CHOICES)
    assert got is None


def test_place_name_starting_with_letter():
    choices = ["A Lưới", "Phong Điền", "Hương Trà", "Phú Lộc"]
    assert extract_letter("A Lưới", choices)[0] == "A"
    assert extract_letter("Xã A Lưới", choices)[0] == "A"
    assert extract_letter("Đáp án: A Lưới", choices)[0] == "A"
    choices2 = ["Phong Điền", "A Lưới", "Hương Trà", "Phú Lộc"]
    assert extract_letter("A Lưới", choices2)[0] == "B"
    assert extract_letter("Đáp án: A Lưới", choices2)[0] == "B"
    assert extract_letter("B", choices2)[0] == "B"


def test_substring_choices():
    choices = ["An Phú", "Tân An Phú", "Phú An", "An Thạnh"]
    assert extract_letter("Tân An Phú", choices)[0] == "B"
    assert extract_letter("An Phú", choices)[0] == "A"
    assert extract_letter("Thuộc xã Tân An Phú", choices)[0] == "B"


# --------------------------------------------------------------- MCQ labels

@pytest.mark.parametrize(
    "raw,label",
    [("B", "correct"), ("A", "outdated"), ("C", "other_wrong"), ("D", "other_wrong"),
     ("không rõ", "invalid"), ("", "invalid")],
)
def test_mcq_labels(raw, label):
    assert score(mcq(), raw).label == label


def test_mcq_old_answer_null_and_text():
    assert score(mcq(old=None), "A").label == "other_wrong"
    assert score(mcq(old="Bình Dương"), "A").label == "outdated"
    assert score(mcq(old="Tỉnh Bình Dương"), "A").label == "outdated"


def test_mcq_old_equals_answer_is_correct():
    assert score(mcq(answer="B", old="B"), "B").label == "correct"


def test_mcq_legacy_distractor():
    it = mcq(answer="A", old=None, choices=["Huế", "Thừa Thiên Huế", "Đà Nẵng", "Quảng Trị"])
    assert score(it, "B").label == "outdated"
    assert score(it, "B").match_detail == "legacy_name"
    assert score(it, "C").label == "other_wrong"


# --------------------------------------------------------------- short answers

@pytest.mark.parametrize(
    "raw",
    [
        "Thành phố Hồ Chí Minh",
        "TP.HCM",
        "TP HCM",
        "TPHCM",
        "Tp. Hồ Chí Minh",
        "Hồ Chí Minh",
        "thành phố hồ chí minh.",
        "Đáp án: TP. Hồ Chí Minh",
        "**Thành phố Hồ Chí Minh**",
        "<think>\n\n</think>\n\nThành phố Hồ Chí Minh",
        "TP.HCM (trước đây thuộc tỉnh Bình Dương)",
        "Xã này hiện thuộc Thành phố Hồ Chí Minh.",
        "Ho Chi Minh City",
    ],
)
def test_short_correct(raw):
    r = score(short("Thành phố Hồ Chí Minh", old="Bình Dương"), raw)
    assert r.label == "correct", (raw, r)
    assert r.correct_nodiac is True


@pytest.mark.parametrize("raw", ["Bình Dương", "Tỉnh Bình Dương", "tỉnh bình dương.", "Thuộc tỉnh Bình Dương"])
def test_short_outdated(raw):
    assert score(short("Thành phố Hồ Chí Minh", old="Bình Dương"), raw).label == "outdated"


def test_short_saigon_is_not_hcm():
    r = score(short("Thành phố Hồ Chí Minh", old="Bình Dương"), "Sài Gòn")
    assert r.label == "other_wrong"
    assert r.match_detail == "soft_alias"
    # ...but a ward literally named Sài Gòn is matched normally
    assert score(short("Phường Sài Gòn", old="Phường Bến Nghé"), "Phường Sài Gòn").label == "correct"
    assert score(short("Phường Sài Gòn", old="Phường Bến Nghé"), "Sài Gòn").label == "correct"
    assert score(short("Phường Sài Gòn", old="Phường Bến Nghé"), "Bến Nghé").label == "outdated"
    # aliases are gold-side only: gold Sài Gòn ward must not accept TP.HCM
    assert score(short("Phường Sài Gòn"), "TP.HCM").label == "other_wrong"


def test_short_hue_legacy():
    r = score(short("Thành phố Huế", old=None), "Thừa Thiên Huế")
    assert r.label == "outdated" and r.match_detail == "legacy_name"
    assert score(short("Huế"), "Tỉnh Thừa Thiên - Huế").label == "outdated"
    assert score(short("Huế"), "Thành phố Huế").label == "correct"
    assert score(short("Huế"), "TP. Huế").label == "correct"


def test_short_old_equals_answer():
    assert score(short("Hà Nội", old="Hà Nội"), "Hà Nội").label == "correct"
    assert score(short("Hà Nội", old="Hà Nội"), "Thủ đô Hà Nội").label == "correct"


def test_short_tone_and_aliases():
    assert score(short("Hòa Bình"), "Hoà Bình").label == "correct"
    assert score(short("Phường Thủy Nguyên"), "Thuỷ Nguyên").label == "correct"
    it = short("Phường Bến Thành", aliases=["Bến Thành"])
    assert score(it, "phường bến thành").label == "correct"


def test_short_diacritics_only_counts_in_nodiac():
    r = score(short("Thành phố Hồ Chí Minh", old="Bình Dương"), "Ho Chi Minh")
    assert r.label == "other_wrong"
    assert r.correct_nodiac is True
    r = score(short("Phường Bến Nghé"), "Phuong Ben Nghe")
    assert r.label == "other_wrong" and r.correct_nodiac is True
    r = score(short("Phường Bến Nghé"), "Ben Thanh")
    assert r.correct_nodiac is False


def test_short_invalid():
    assert score(short("Đồng Nai"), "").label == "invalid"
    assert score(short("Đồng Nai"), "Tôi không biết.").label == "invalid"
    assert score(short("Đồng Nai"), "<think>Hmm").label == "invalid"
    assert score(short("Đồng Nai"), "Không có thông tin").label == "invalid"


def test_short_other_wrong():
    r = score(short("Đồng Nai", old="Bình Phước"), "Tây Ninh")
    assert r.label == "other_wrong"
    assert r.parsed == "Tây Ninh"


def test_short_substring_not_confused():
    # exact "Tân An Phú" must not count as "An Phú"
    assert score(short("An Phú", old="Tân An Phú"), "Tân An Phú").label == "outdated"
    assert score(short("Tân An Phú", old="An Phú"), "An Phú").label == "outdated"


def test_short_relation_sentences():
    it = short("Thành phố Hồ Chí Minh", old="Bình Dương")
    # past-tense clause ignored, present clause scored
    assert score(it, "Trước đây thuộc tỉnh Bình Dương và bây giờ thuộc Thành phố Hồ Chí Minh").label == "correct"
    assert score(it, "Hiện thuộc TP.HCM, trước đây thuộc Bình Dương").label == "correct"
    # echo of the (old) question subject before the verb is ignored
    assert score(it, "Bình Dương (cũ) thuộc Thành phố Hồ Chí Minh.").label == "correct"
    assert score(it, "Tỉnh Bình Dương (cũ) nay thuộc tỉnh Bình Dương.").label == "outdated"
    assert score(it, "Tỉnh Bình Dương được sáp nhập vào TP. Hồ Chí Minh").label == "correct"
    assert score(it, "Xã Tân Uyên thuộc tỉnh Đồng Nai").label == "other_wrong"
    # two present-tense claims -> ambiguous
    r = score(it, "Xã này thuộc Bình Dương và thuộc TP.HCM")
    assert r.label == "other_wrong" and r.match_detail == "ambiguous"
    # unchanged province: old == gold never yields ambiguous
    it2 = short("Hà Nội", old="Hà Nội")
    assert score(it2, "Phường Tràng Tiền (cũ) thuộc tỉnh Hà Nội.").label == "correct"
    # ward answers
    it3 = short("Phường Sài Gòn", old="Phường Bến Nghé")
    assert score(it3, "Phường Bến Nghé (cũ) nay là phường Sài Gòn.").label == "correct"
    assert score(it3, "Phường Bến Nghé nay vẫn là phường Bến Nghé").label == "outdated"
    assert score(it3, "Phường Sài Gòn là phường mới thành lập").label == "correct"
    r = score(it3, "Phường Bến Nghé được đổi tên thành phường Bến Thành")
    assert r.label == "other_wrong"


def test_short_numbered_wards_no_containment():
    # "1" is too short for substring containment
    r = score(short("Phường 1", old="Phường 3"), "Phường 12 thuộc quận 1")
    assert r.label == "other_wrong"
    assert score(short("Phường 1", old="Phường 3"), "Phường 01").label == "correct"
    assert score(short("Phường 1", old="Phường 3"), "Phường 3").label == "outdated"


def test_short_address_segments():
    it = short("Phường Sài Gòn, Thành phố Hồ Chí Minh",
               old="Phường Bến Nghé, Quận 1, Thành phố Hồ Chí Minh")
    assert score(it, "Phường Sài Gòn, TP.HCM").label == "correct"
    assert score(it, "phường Sài Gòn, thành phố Hồ Chí Minh, Việt Nam").label == "correct"
    r = score(it, "45 Lê Duẩn, Phường Sài Gòn, TP.HCM")
    assert r.label == "correct" and r.match_detail == "address_suffix"
    assert score(it, "Phường Bến Nghé, Quận 1, TP. Hồ Chí Minh").label == "outdated"
    assert score(it, "Phường Bến Thành, TP.HCM").label == "other_wrong"
    # wrong province segment
    assert score(it, "Phường Sài Gòn, Bình Dương").label == "other_wrong"


def test_short_address_legacy():
    it = short("Phường Thuận Hóa, Thành phố Huế")
    r = score(it, "Phường Thuận Hóa, Thừa Thiên Huế")
    assert r.label == "outdated" and r.match_detail == "legacy_name"


def test_clean_output():
    assert clean_output("<think>abc</think>\n\nB") == "B"
    assert clean_output("**B**") == "B"
    assert clean_output(None) == ""


def test_short_numeric():
    it = short("34", aliases=["34 tỉnh, thành phố"], old="63")
    assert score(it, "34").label == "correct"
    assert score(it, "Có 34 tỉnh, thành phố.").label == "correct"
    assert score(it, "34 tỉnh, thành phố").label == "correct"
    assert score(it, "63 tỉnh thành").label == "outdated"
    # "từ 63 ... xuống 34": 63 is the past value (deliberate change, see SPEC numeric rule)
    assert score(it, "Từ 63 tỉnh thành giảm xuống 34").label == "correct"
    assert score(it, "Có 34 hoặc 63 tỉnh").match_detail == "ambiguous"
    assert score(it, "35").label == "other_wrong"
    assert score(it, "không biết").label == "invalid"


def test_ward_named_after_province():
    # "Phường Bình Dương" is a real post-2025 ward of TP.HCM; a bare "Bình Dương" is
    # ambiguous with the old province and must not be accepted.
    it = short("Phường Bình Dương", old="Phường Phú Cường")
    assert score(it, "Phường Bình Dương").label == "correct"
    assert score(it, "phuong Binh Duong").correct_nodiac is True
    r = score(it, "Bình Dương")
    assert r.label == "other_wrong" and r.match_detail == "ambiguous_province_name"
    assert score(it, "Tỉnh Bình Dương").label == "other_wrong"
    assert score(it, "Nay là phường Bình Dương.").label == "correct"
    assert score(it, "Nay thuộc tỉnh Bình Dương").label != "correct"
    assert score(it, "Phường Phú Cường").label == "outdated"
    # address form
    it2 = short("Phường Bình Dương, Thành phố Hồ Chí Minh")
    assert score(it2, "Phường Bình Dương, TP.HCM").label == "correct"
    assert score(it2, "Bình Dương, TP.HCM").label == "other_wrong"


def test_level_mismatch_numbered():
    it = short("Phường 1", old="Phường 3")
    assert score(it, "Quận 1").label == "other_wrong"
    assert score(it, "Quận 1").match_detail == "level_mismatch"
    assert score(it, "1").label == "correct"
    assert score(it, "Xã 1").label == "correct"  # same level; within-province names are unique


def test_outdated_first_segment_with_gold_later():
    it = short("Thành phố Hồ Chí Minh", old="Bình Dương")
    assert score(it, "Bình Dương, nay thuộc TP. Hồ Chí Minh").label == "correct"
    r = score(it, "Bình Dương, gần TP. Hồ Chí Minh")
    assert r.label == "other_wrong" and r.match_detail == "ambiguous"
    assert score(it, "Bình Dương, gần Đồng Nai").label == "outdated"
    assert score(it, "Bình Dương, Việt Nam").label == "outdated"
    assert score(it, "TP. Hồ Chí Minh (trước đây là Bình Dương)").label == "correct"
