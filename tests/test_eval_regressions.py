"""Regression tests for the eval-harness review findings (fixer pass)."""

import json
from datetime import date

import pytest

from viadmin.eval import runner
from viadmin.eval.backends import FakeBackend
from viadmin.eval.scorer import extract_letter, score


def short(answer, old=None, aliases=(), diac=None):
    meta = {} if diac is None else {"has_diacritics": diac}
    return {"id": "s", "format": "short", "choices": None, "answer": answer,
            "answer_aliases": list(aliases), "old_answer": old, "meta": meta}


def mcq(choices, answer, old=None):
    return {"id": "m", "format": "mcq", "choices": list(choices), "answer": answer,
            "answer_aliases": [], "old_answer": old, "meta": {}}


def L(item, raw):
    r = score(item, raw)
    return r.label, r.match_detail


# ------------------------------------------------------------- runner (findings 1, 9)

ITEMS = [
    dict(id="i1", qtype="T1_membership", format="short", question="Q1?", answer="Thành phố Hồ Chí Minh",
         answer_aliases=[], old_answer="Tỉnh Bình Dương", choices=None, meta={}),
    dict(id="i2", qtype="T4_address", format="short", question="Q2?",
         answer="Phường Sài Gòn, Thành phố Hồ Chí Minh", answer_aliases=[], old_answer=None, choices=None, meta={}),
    dict(id="i3", qtype="T1_membership", format="mcq", question="Q3?", answer="B", choices=["a", "b", "c", "d"],
         answer_aliases=[], old_answer=None, meta={}),
]


def test_filtered_rerun_keeps_other_predictions(tmp_path):
    out = tmp_path / "r"
    be = FakeBackend(lambda m: "B", name="m1")
    runner.run(be, ITEMS, ["closed"], out, log=lambda s: None)
    # what `--qtypes T4_address` does: run() sees only the filtered items
    s = runner.run(be, [ITEMS[1]], ["closed"], out, log=lambda s: None)
    rows = runner.read_jsonl(out / "predictions.jsonl")
    assert sorted(r["item_id"] for r in rows) == ["i1", "i2", "i3"]
    assert s["n_unscored_predictions"] == 2  # without score_items they are kept, not scored
    s = runner.run(be, [ITEMS[1]], ["closed"], out, log=lambda s: None, score_items=ITEMS)
    assert s["n_predictions"] == 3 and s["n_unscored_predictions"] == 0


def test_rescore_keeps_unknown_rows(tmp_path):
    out = tmp_path / "r"
    runner.run(FakeBackend(lambda m: "B", name="m1"), ITEMS, ["closed"], out, log=lambda s: None)
    s = runner.rescore(out, {"i2": ITEMS[1]}, log=lambda s: None)
    assert len(runner.read_jsonl(out / "predictions.jsonl")) == 3
    assert s["n_predictions"] == 1 and s["n_unscored_predictions"] == 2


def test_cli_qtypes_rerun_scores_full_items(monkeypatch, tmp_path):
    import viadmin.eval.backends as B

    monkeypatch.setattr(B, "make_backend", lambda kind, model, **kw: FakeBackend(lambda m: "B", name=model))
    items = tmp_path / "items.jsonl"
    items.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ITEMS), encoding="utf-8")
    out = tmp_path / "cli"
    base = ["--model", "fake", "--items", str(items), "--contexts", str(tmp_path / "none.jsonl"),
            "--passages", str(tmp_path / "none.jsonl"), "--out", str(out)]
    assert runner.main(base) == 0
    assert runner.main(base + ["--qtypes", "T4_address"]) == 0
    s = json.loads((out / "scores.json").read_text())
    assert s["n_predictions"] == 3 and s["n_unscored_predictions"] == 0


def test_resume_refuses_changed_prompt(tmp_path):
    out = tmp_path / "r"
    be = FakeBackend(lambda m: "B", name="m1")
    runner.run(be, ITEMS, ["closed+sysdate"], out, log=lambda s: None)
    with pytest.raises(SystemExit):
        runner.run(be, ITEMS, ["closed+sysdate"], out, log=lambda s: None, today=date(2025, 1, 1))
    changed = [dict(ITEMS[0], question="Q1 changed?"), *ITEMS[1:]]
    with pytest.raises(SystemExit):
        runner.run(be, changed, ["closed+sysdate"], out, log=lambda s: None)
    # identical prompt: resumes without generating
    be2 = FakeBackend(lambda m: "B", name="m1")
    runner.run(be2, ITEMS, ["closed+sysdate"], out, log=lambda s: None)
    assert be2.calls == 0
    cfg = json.loads((out / "run_config.json").read_text())
    assert len(cfg["previous_runs"]) >= 1 and cfg["today"] == "2026-10-13"


# ------------------------------------------------- admin levels in matching (finding 2)

@pytest.mark.parametrize("gold,old,pred", [
    ("Phường Hoàn Kiếm", "Phường Hàng Trống", "Quận Hoàn Kiếm"),
    ("Phường Hoàn Kiếm", "Phường Hàng Trống", "Huyện Hoàn Kiếm"),
    ("Phường Bến Cát", "Phường Mỹ Phước", "Thị xã Bến Cát"),
    ("Phường Vũng Tàu", "Phường 1", "Thành phố Vũng Tàu"),
    ("Phường Thủ Dầu Một", "Phường Phú Cường", "Thành phố Thủ Dầu Một"),
    ("Phường Thủ Dầu Một", "Phường Phú Cường", "TP. Thủ Dầu Một"),
    ("Phường Vũng Tàu", "Phường 1", "Tỉnh Bà Rịa - Vũng Tàu"),
    ("Phường Vũng Tàu", "Phường 1", "Bà Rịa - Vũng Tàu"),
    ("Phường Bà Rịa", "Phường Phước Hiệp", "Bà Rịa - Vũng Tàu"),
    ("Phường Bà Rịa", "Phường Phước Hiệp", "Tỉnh Bà Rịa - Vũng Tàu"),
    ("Phường Hoàn Kiếm", "Phường Hàng Trống", "Phường Hàng Trống thuộc quận Hoàn Kiếm"),
])
def test_old_district_or_province_is_not_the_new_ward(gold, old, pred):
    assert score(short(gold, old), pred).label != "correct"


@pytest.mark.parametrize("pred,label", [
    ("Thành phố Vũng Tàu", "other_wrong"),
    ("Tỉnh Bà Rịa - Vũng Tàu", "other_wrong"),
    ("Vũng Tàu", "correct"),
    ("Phường Vũng Tàu", "correct"),
])
def test_unprefixed_alias_inherits_gold_level(pred, label):
    assert score(short("Phường Vũng Tàu", "Phường 1", aliases=["Vũng Tàu"]), pred).label == label


def test_ward_gold_still_matches_with_ward_prefix():
    it = short("Phường Hoàn Kiếm", "Phường Hàng Trống")
    assert L(it, "Phường Hoàn Kiếm")[0] == "correct"
    assert L(it, "Hoàn Kiếm")[0] == "correct"
    assert L(it, "Nay là phường Hoàn Kiếm")[0] == "correct"
    assert L(it, "Phường Hàng Trống nay thuộc phường Hoàn Kiếm, Hà Nội")[0] == "correct"
    assert L(it, "P. Hoàn Kiếm")[0] == "correct"
    assert L(it, "Quận Hoàn Kiếm") == ("other_wrong", "level_mismatch")


def test_hyphenated_names_are_not_split():
    it = short("Phường Văn Miếu - Quốc Tử Giám, Thành phố Hà Nội")
    assert L(it, "Phường Văn Miếu - Quốc Tử Giám, Thành phố Hà Nội")[0] == "correct"
    assert L(it, "Phường Văn Miếu - Quốc Tử Giám - Thành phố Hà Nội")[0] == "correct"
    it2 = short("Phường Lâm Viên - Đà Lạt", "Phường 1")
    assert L(it2, "Lâm Viên - Đà Lạt")[0] == "correct"
    assert L(it2, "Phường Lâm Viên")[0] != "correct"


# ------------------------------------- ward named after the old province (finding 4)

@pytest.mark.parametrize("pred", [
    "Phường Bình Dương, Thành phố Hồ Chí Minh",
    "Phường Bình Dương, TP.HCM",
    "Phường Bình Dương thuộc Thành phố Hồ Chí Minh",
])
def test_province_gold_with_ward_named_after_old_province(pred):
    assert score(short("Thành phố Hồ Chí Minh", "Tỉnh Bình Dương"), pred).label == "correct"
    assert score(short("Thành phố Hồ Chí Minh", "Bình Dương"), pred).label == "correct"


def test_bac_kan_ward_in_thai_nguyen():
    it = short("Tỉnh Thái Nguyên", "Tỉnh Bắc Kạn")
    assert L(it, "Phường Bắc Kạn, Tỉnh Thái Nguyên")[0] == "correct"
    assert L(it, "Tỉnh Bắc Kạn")[0] == "outdated"
    assert L(it, "Phường Bắc Kạn, Tỉnh Bắc Kạn")[0] == "outdated"


# --------------------------------------------------------- MCQ (findings 3, 10)

def test_letterish_choice_does_not_override_explicit_letter():
    ch = ["Xã A Lưới 1", "Xã Phú Lộc", "Xã Hương Trà", "Xã Quảng Điền"]
    assert extract_letter("Đáp án: C, vì Xã A Lưới 1 đã bị đổi tên", ch)[0] == "C"
    assert extract_letter("C. Xã Hương Trà (không phải Xã A Lưới 1)", ch)[0] == "C"
    assert extract_letter("Xã A Lưới 1", ch)[0] == "A"
    assert extract_letter("Đáp án: A Lưới 1", ch)[0] == "A"
    ch2 = ["Xã Phú Lộc", "Xã A Lưới 1", "Xã Hương Trà", "Xã Quảng Điền"]
    assert extract_letter("Đáp án: A Lưới 1", ch2)[0] == "B"
    assert extract_letter("Đáp án: A", ch2)[0] == "A"


@pytest.mark.parametrize("raw,letter", [
    ("Đáp án là b", "B"),
    ("đáp án: b", "B"),
    ("đáp án: b.", "B"),
    ("TP.HCM", "B"),
    ("Tỉnh Bình Dương đã sáp nhập vào Thành phố Hồ Chí Minh", "B"),
])
def test_mcq_minor_forms(raw, letter):
    ch = ["Tỉnh Bình Dương", "Thành phố Hồ Chí Minh", "Tỉnh Đồng Nai", "Tỉnh Tây Ninh"]
    assert extract_letter(raw, ch)[0] == letter


def test_mcq_lowercase_in_running_text_not_a_letter():
    ch = ["Tỉnh Bình Dương", "Thành phố Hồ Chí Minh", "Tỉnh Đồng Nai", "Tỉnh Tây Ninh"]
    assert extract_letter("Đáp án là bình dương", ch)[0] == "A"  # by text, not letter "b"


# ------------------------------------------------------------ addresses (finding 5)

T4 = short("Phường Sài Gòn, Thành phố Hồ Chí Minh", "Phường Bến Nghé, Quận 1, Thành phố Hồ Chí Minh")


@pytest.mark.parametrize("pred", [
    "Phường Sài Gòn thuộc Thành phố Hồ Chí Minh",
    "Phường Sài Gòn, thuộc Thành phố Hồ Chí Minh",
    "Phường Sài Gòn (Thành phố Hồ Chí Minh)",
    "Phường Sài Gòn - Thành phố Hồ Chí Minh",
    "Địa chỉ mới: Phường Sài Gòn, Thành phố Hồ Chí Minh",
    "Địa chỉ mới là Phường Sài Gòn, Thành phố Hồ Chí Minh",
    "Phường Sài Gòn, Thành phố Hồ Chí Minh (trước đây là Phường Bến Nghé, Quận 1)",
    "Phường Sài Gòn, Thành phố Hồ Chí Minh, trước đây là Phường Bến Nghé, Quận 1",
    "P. Sài Gòn, TP.HCM",
    "Phường Bến Nghé, Quận 1, TP.HCM nay là Phường Sài Gòn, TP.HCM",
    "Phường Bến Nghé, Quận 1 được sáp nhập vào Phường Sài Gòn, Thành phố Hồ Chí Minh",
])
def test_t4_sentence_forms_correct(pred):
    assert score(T4, pred).label == "correct", score(T4, pred)


def test_t4_outdated_and_partial():
    assert L(T4, "Phường Bến Nghé, Thành phố Hồ Chí Minh")[0] == "outdated"
    assert L(T4, "Phường Bến Nghé, Quận 1, TP. Hồ Chí Minh")[0] == "outdated"
    assert L(T4, "Phường Sài Gòn, Quận 1, Thành phố Hồ Chí Minh") == ("other_wrong", "extra_district")
    assert L(T4, "Phường Sài Gòn") == ("other_wrong", "partial")
    it = short("Phường Phú Cường, Thành phố Hồ Chí Minh", "Phường Phú Cường, Thành phố Thủ Dầu Một, Tỉnh Bình Dương")
    assert L(it, "Phường Phú Cường, Tỉnh Bình Dương")[0] == "outdated"
    assert L(it, "Phường Phú Cường, TP HCM")[0] == "correct"
    # province unchanged, ward unchanged: dropping the district gives the gold -> correct
    it2 = short("Phường Tràng Tiền, Thành phố Hà Nội", "Phường Tràng Tiền, Quận Hoàn Kiếm, Thành phố Hà Nội")
    assert L(it2, "Phường Tràng Tiền, Thành phố Hà Nội")[0] == "correct"
    assert L(it2, "Phường Tràng Tiền, Quận Hoàn Kiếm, Thành phố Hà Nội")[0] == "outdated"


# -------------------------------------------------------------- numbers (finding 6)

@pytest.mark.parametrize("gold,old,pred,label", [
    ("3321", "10035", "3.321", "correct"),
    ("3321", "10035", "3,321", "correct"),
    ("3321", "10035", "3.321 đơn vị hành chính cấp xã", "correct"),
    ("3321", "10035", "10.035", "outdated"),
    ("7", None, "Từ 1/7/2025 có 6 đơn vị", "other_wrong"),
    ("7", None, "Theo Nghị quyết 202/2025/QH15 có 6", "other_wrong"),
    ("34", "63", "34 (trước đây là 63)", "correct"),
    ("34", "63", "Việt Nam hiện có 34 tỉnh thành, giảm từ 63", "correct"),
    ("34", "63", "Trước ngày 1/7/2025 có 63 tỉnh, nay còn 34", "correct"),
    ("34", "63", "Từ ngày 1/7/2025, cả nước có 34 tỉnh, thành phố.", "correct"),
    ("34", "63", "63 tỉnh thành", "outdated"),
])
def test_numeric(gold, old, pred, label):
    assert score(short(gold, old), pred).label == label


# -------------------------------------------------------- no-diacritics (finding 7)

def test_label_nodiac():
    it = short("Thành phố Hồ Chí Minh", "Tỉnh Bình Dương")
    r = score(it, "Binh Duong")
    assert r.label == "other_wrong" and r.label_nodiac == "outdated" and r.correct_nodiac is False
    r = score(it, "Phuong Phu Cuong nay thuoc TP HCM")
    assert r.label_nodiac == "correct"
    r = score(it, "Phuong Phu Cuong truoc day thuoc tinh Binh Duong, nay thuoc TP HCM")
    assert r.label_nodiac == "correct"
    hue = short("Thành phố Huế")
    r = score(hue, "Thua Thien Hue")
    assert r.label_nodiac == "outdated" and r.correct_nodiac is False
    assert score(hue, "Thanh pho Hue").label_nodiac == "correct"


def test_no_diacritic_items_use_nodiac_label():
    it = short("Thành phố Hồ Chí Minh", "Tỉnh Bình Dương", diac=False)
    r = score(it, "Binh Duong")
    assert r.label == "outdated" and r.label_strict == "other_wrong"
    assert score(it, "Thanh pho Ho Chi Minh").label == "correct"
    assert score(it, "Thành phố Hồ Chí Minh").label == "correct"


def test_metrics_nodiac_rates():
    from viadmin.eval.metrics import stats
    rows = [{"label": "other_wrong", "label_nodiac": "outdated", "format": "short"},
            {"label": "correct", "label_nodiac": "correct", "format": "short"},
            {"label": "correct", "label_nodiac": None, "format": "mcq"}]
    s = stats(rows)
    assert s["accuracy_nodiac"] == 2 / 3 and s["outdated_rate_nodiac"] == 1 / 3


# ------------------------------------------------------------ abstain (finding 8)

def test_na_place_names_are_not_abstentions():
    it = short("Tỉnh Thái Nguyên", "Tỉnh Bắc Kạn")
    assert L(it, "Na Rì thuộc tỉnh Thái Nguyên")[0] == "correct"
    assert L(it, "Na Rì, tỉnh Thái Nguyên")[0] == "correct"
    assert L(it, "N/A") == ("invalid", "abstain")
    assert L(it, "NA.") == ("invalid", "abstain")
    assert L(short("Xã Na Rì", "Xã Kim Lư"), "Na Rì")[0] == "correct"


def test_hedged_answers_are_scored():
    it = short("Thành phố Hồ Chí Minh", "Tỉnh Bình Dương")
    assert L(it, "Không chắc, nhưng có lẽ là Thành phố Hồ Chí Minh")[0] == "correct"
    assert L(it, "Tôi không chắc chắn, có thể là tỉnh Bình Dương")[0] == "outdated"
    assert L(it, "Không chắc")[0] == "invalid"
    assert L(it, "Tôi không biết phường này hiện nay thuộc tỉnh nào")[0] == "invalid"


# --------------------------------------------------------------- order (finding 10)

def test_two_names_ambiguous_in_both_orders():
    it = short("Thành phố Hồ Chí Minh", "Tỉnh Bình Dương")
    assert L(it, "Thành phố Hồ Chí Minh, tỉnh Bình Dương") == ("other_wrong", "ambiguous")
    assert L(it, "Tỉnh Bình Dương, Thành phố Hồ Chí Minh") == ("other_wrong", "ambiguous")
    assert L(it, "Thành phố Hồ Chí Minh (trước đây: tỉnh Bình Dương)")[0] == "correct"
    assert L(it, "Phường Phú Cường trước thuộc tỉnh Bình Dương, nay thuộc Thành phố Hồ Chí Minh")[0] == "correct"


def test_validate_flags_nodiac_collisions():
    from viadmin.eval.validate import lint_item
    it = {"id": "x", "qtype": "T1_membership", "question": "Q?", "format": "short", "choices": None,
          "answer": "Xã Tân Thành", "answer_aliases": [], "old_answer": "Xã Tân Thạnh",
          "meta": {"has_diacritics": False}}
    assert any("identical without diacritics" in e for e in lint_item(it))
    it["meta"]["has_diacritics"] = True
    assert lint_item(it) == []
    m = {"id": "y", "qtype": "T1_membership", "question": "Q?", "format": "mcq", "answer": "A",
         "choices": ["Xã Tân Thành", "Xã Tân Thạnh", "Xã Phú Mỹ", "Xã An Phú"], "old_answer": None,
         "meta": {"has_diacritics": False}}
    assert any("collide without diacritics" in e for e in lint_item(m))


# ------------------------------------------- question echo on unchanged items (finding 11)

VB = short("Xã Vụ Bổn")  # unchanged ward: no old answer, the gold is in the question


@pytest.mark.parametrize("pred", [
    "Xã Vụ Bổn được sáp nhập vào xã Krông Pắc.",
    "Xã Vụ Bổn (huyện Krông Pắc) nay thuộc xã Krông Pắc, tỉnh Đắk Lắk",
    "Xã Vụ Bổn được sáp nhập thành xã Krông Pắc",
    "Xã Vụ Bổn, huyện Krông Pắc, tỉnh Đắk Lắk thuộc xã Krông Pắc, tỉnh Đắk Lắk.",
    "Xã Vụ Bổn thuộc đơn vị hành chính cấp xã là: xã Krông Pắc.",
    "Xã Vụ Bổn, xã Ea Kly và xã Ea Kuăng được sáp nhập thành xã Ea Kly.",
    "Xã Vụ Bổn được sáp nhập cùng xã Ea Kly để thành lập xã Ea Kly mới",
    "Xã Vụ Bổn thuộc xã Krông Pắc? Tôi không chắc chắn về thông tin này.",
])
def test_subject_echo_not_credited_when_another_unit_is_named(pred):
    assert L(VB, pred) == ("other_wrong", "relation"), L(VB, pred)
    # the same, with the answer repeated alone on the last line (scored on that line)
    assert L(VB, pred + "\n\nXã Ea Kly, tỉnh Đắk Lắk")[0] == "other_wrong"


@pytest.mark.parametrize("pred,label,detail", [
    ("Xã Vụ Bổn là xã mới thành lập", "correct", "subject_segment"),
    ("Xã Vụ Bổn thuộc đơn vị hành chính cấp xã", "correct", "subject_segment"),
    ("Xã Vụ Bổn thuộc tỉnh Đắk Lắk", "correct", "subject_segment"),
    ("Xã Vụ Bổn thuộc đơn vị hành chính cấp xã: Xã Vụ Bổn", "correct", "relation_contained"),
    ("Xã Vụ Bổn, tỉnh Đắk Lắk", "correct", "first_segment"),
    ("Xã Vụ Bổn được sáp nhập với xã Ea Kly thành xã Vụ Bổn mới", "correct", "relation_contained"),
    ("Xã Vụ Bổn được sáp nhập cùng xã Ea Kly để thành lập xã Vụ Bổn", "correct", "relation"),
    ("Vẫn là xã Vụ Bổn", "correct", "relation"),
])
def test_subject_or_tail_naming_the_gold_still_counts(pred, label, detail):
    assert L(VB, pred) == (label, detail)


def test_unchanged_province_with_merger_partner_in_parenthesis():
    it = short("Thành phố Đà Nẵng")
    assert L(it, "Thành phố Đà Nẵng (đơn vị hành chính cấp tỉnh, sau sáp nhập với tỉnh Quảng Nam)")[0] == "correct"
    assert L(it, "Thành phố Đà Nẵng (thành phố trực thuộc trung ương)")[0] == "correct"
    assert L(it, "Đà Nẵng là thành phố thuộc tỉnh Quảng Nam.")[0] == "other_wrong"
    it2 = short("Tỉnh Lào Cai")
    assert L(it2, "Tỉnh Lào Cai được sáp nhập với tỉnh Yên Bái thành tỉnh Lào Cai... nhưng tôi không chắc chắn.") == ("correct", "relation")


# ------------------------------------------------ merger verbs and dual answers (finding 12)

NP = short("Xã Chợ Đồn", "Xã Ngọc Phái")


@pytest.mark.parametrize("pred,label", [
    ("Xã Ngọc Phái (huyện Chợ Đồn, tỉnh Bắc Kạn) được sáp nhập thành xã Bằng Phúc, tỉnh Thái Nguyên.", "other_wrong"),
    ("Xã Ngọc Phái (huyện Chợ Đồn) được sắp xếp vào xã Bằng Phúc từ ngày 1/7/2025, nên đơn vị hiện nay là:\n\nXã Bằng Phúc", "other_wrong"),
    ("Xã Ngọc Phái được sắp xếp vào xã Chợ Đồn", "correct"),
    ("Xã Ngọc Phái được sáp nhập thành xã Chợ Đồn, tỉnh Thái Nguyên.", "correct"),
    ("Xã Ngọc Phái sáp nhập với thị trấn Bằng Lũng và xã Bằng Lãng để thành lập xã Chợ Đồn", "correct"),
    ("Xã Ngọc Phái cùng thị trấn Bằng Lũng hợp nhất thành xã Chợ Đồn.\n\nĐáp án: Xã Chợ Đồn, tỉnh Thái Nguyên", "correct"),
    ("Xã Ngọc Phái, huyện Chợ Đồn, tỉnh Bắc Kạn", "outdated"),
    ("Xã Ngọc Phái vẫn là xã Ngọc Phái", "outdated"),
])
def test_merger_verbs_score_the_destination(pred, label):
    assert L(NP, pred)[0] == label, L(NP, pred)


def test_merger_clause_does_not_cross_a_city_name():
    it = short("Phường Sài Gòn", "Phường Bến Nghé")
    # "thành" of "thành phố" does not end a "sáp nhập với ... thành" clause
    assert L(it, "Phường Bến Nghé sáp nhập với phường Đa Kao, thành phố Hồ Chí Minh")[0] != "correct"


def test_mcq_relation_tail_with_abbreviated_choice():
    ch = ["Tỉnh Đồng Nai", "Tỉnh Bà Rịa - Vũng Tàu", "Tỉnh Lâm Đồng", "Thành phố Hồ Chí Minh"]
    assert extract_letter("Tỉnh Bà Rịa - Vũng Tàu sáp nhập vào TP.HCM.", ch) == ("D", "choice_text_relation")
    assert extract_letter("Xã này thuộc TP.HCM", ch)[0] == "D"
    ch2 = ["Xã Lý Nhân", "Xã Nam Xang", "Xã Công Lý", "Xã Vĩnh Trụ"]
    assert extract_letter("Theo nghị quyết, xã Công Lý, Nhân Thắng... sáp nhập thành xã Nam Xang (Ninh Bình).", ch2)[0] == "B"


# ------------------------------------------------------------- abstentions (finding 13)

@pytest.mark.parametrize("pred", [
    "Tôi không có đủ thông tin chắc chắn về việc sắp xếp năm 2025 đối với xã Ngọc Phái, nên không thể xác nhận đơn vị mới.",
    "Tôi chưa chắc chắn về thông tin này nên không thể trả lời chính xác. Theo hiểu biết của tôi, xã Ngọc Phái được nhập vào xã nào đó.",
    "Tôi không thể xác nhận đơn vị hành chính của xã Ngọc Phái.",
    "Tôi không nắm rõ xã Ngọc Phái thuộc đơn vị nào.",
    "Xã Ngọc Phái không còn tồn tại độc lập sau sắp xếp; tôi không chắc chắn về đơn vị sáp nhập cụ thể nên không thể xác nhận.",
    "Xã Ngọc Phái không còn tồn tại như một đơn vị độc lập. Tôi không có thông tin chắc chắn về việc sáp nhập cụ thể.",
    "Xã Ngọc Phái đã được sáp nhập; tôi không chắc chắn về đơn vị hành chính cụ thể mới, nên không thể xác nhận tên chính xác.",
    "Xã Ngọc Phái đã được sắp xếp lại. Tôi không thể khẳng định tên đơn vị mới.",
])
def test_abstention_with_echoed_name_is_invalid(pred):
    assert L(NP, pred) == ("invalid", "abstain"), L(NP, pred)
    assert L(VB, pred.replace("Ngọc Phái", "Vụ Bổn")) == ("invalid", "abstain")


@pytest.mark.parametrize("pred,label", [
    ("Không chắc, nhưng có lẽ là xã Chợ Đồn", "correct"),
    ("Tôi không chắc chắn, có thể là xã Ngọc Phái", "outdated"),
    ("Có lẽ là xã Chợ Đồn nhưng tôi không chắc", "correct"),
    ("Xã Chợ Đồn, tỉnh Thái Nguyên.\n\nTôi không hoàn toàn chắc chắn về thông tin này.", "correct"),
    ("Xã Ngọc Phái nay thuộc xã Bằng Phúc.\n\nTôi không chắc chắn tuyệt đối về thông tin này.", "other_wrong"),
])
def test_hedged_or_committed_answers_are_still_scored(pred, label):
    assert L(NP, pred)[0] == label, L(NP, pred)


# ---------------------------------- T4: unchanged two-level address, stale three-level answer

def test_t4_unchanged_address_three_level_answer_is_outdated():
    it = short("Xã Ia Chia, Tỉnh Gia Lai")
    it["meta"].update(old_address="Xã Ia Chia, Huyện Ia Grai, Tỉnh Gia Lai", gold_ward="Xã Ia Chia",
                      gold_province="Tỉnh Gia Lai", old_ward_name="Xã Ia Chia", old_province_name="Tỉnh Gia Lai")
    assert L(it, "Xã Ia Chia, Tỉnh Gia Lai") == ("correct", "address")
    assert L(it, "Xã Ia Chia, Huyện Ia Grai, Tỉnh Gia Lai") == ("outdated", "address")
    assert L(it, "Số 72, thôn 11, xã Ia Chia, huyện Ia Grai, tỉnh Gia Lai") == ("outdated", "address_suffix")
    assert L(it, "Xã Ia Chia, huyện Ia Grai, tỉnh Gia Lai nay là xã Ia Chia, tỉnh Gia Lai")[0] == "correct"
    assert L(it, "Xã Ia Grai, Tỉnh Gia Lai")[0] == "other_wrong"
    r = score(it, "Xã Ia Chia, Huyện Ia Grai, Tỉnh Gia Lai")
    assert r.components == {"ward": "correct", "province": "correct"}
    # without the pre-reform address nothing changes
    assert L(short("Xã Ia Chia, Tỉnh Gia Lai"), "Xã Ia Chia, Huyện Ia Grai, Tỉnh Gia Lai") == ("other_wrong", "extra_district")


# ------------------------------------------- second review of the scorer: regressions and gaps

def test_abstention_lead_in_or_consequence_clause_is_an_abstention():
    # a pure abstention after a sentence adverbial, as a consequence clause, in a
    # parenthetical, or after a question echo whose first segment is the gold
    for pred in [
        "Xã Vụ Bổn, huyện Krông Pắc, tỉnh Đắk Lắk là một đơn vị hành chính cấp xã cũ; sau sắp xếp năm 2025 tôi không chắc chắn về đơn vị mới, nên không thể xác nhận tên cụ thể.",
        "Xã Vụ Bổn, huyện Krông Pắc, tỉnh Đắk Lắk không được xác nhận trong thông tin mà tôi có. Tôi không có thông tin chắc chắn về việc sáp nhập, nên không thể trả lời chính xác.",
        "Xã Vụ Bổn thuộc đơn vị hành chính cấp xã... Tuy nhiên, tôi không thể xác nhận chắc chắn tình trạng hành chính của xã này.",
        "Xã Vụ Bổn không thuộc đơn vị hành chính cấp xã nào sau sắp xếp mà... (xin lưu ý: tôi không có đủ thông tin xác thực về nội dung sắp xếp này).",
        "Xã Vụ Bổn không còn là đơn vị độc lập; hiện không thể xác định chắc chắn tên đơn vị mới.",
    ]:
        assert L(VB, pred) == ("invalid", "abstain"), pred
    # a committed answer with a disclaimer is still scored
    assert L(NP, "Xã Chợ Đồn, tỉnh Thái Nguyên. Tuy nhiên, tôi không chắc chắn về thông tin này.")[0] == "correct"
    assert L(NP, "Xã Chợ Đồn, tỉnh Thái Nguyên\n\nLưu ý: tôi không có đủ thông tin để xác nhận.")[0] == "correct"
    assert L(NP, "Xã Ngọc Phái nay thuộc xã Chợ Đồn.\n\nTuy nhiên, tôi không có thông tin chắc chắn.")[0] == "correct"


def test_relation_clause_naming_the_unit_is_not_voided_by_a_later_disclaimer():
    assert L(NP, "Xã Ngọc Phái hiện thuộc xã Chợ Đồn mới (tỉnh Thái Nguyên). Tôi không chắc chắn về điều này.") == ("correct", "relation_contained")
    assert L(NP, "Xã Ngọc Phái hiện thuộc xã Bằng Phúc mới. Tôi không chắc chắn về điều này.") == ("other_wrong", "relation")


@pytest.mark.parametrize("pred,label", [
    ("Tôi không có đủ thông tin, nhưng có lẽ là xã Chợ Đồn", "correct"),
    ("Tôi không thể xác nhận, nhưng theo tôi là xã Chợ Đồn", "correct"),
    ("Tôi không chắc chắn về điều này, nhưng có thể là xã Ngọc Phái", "outdated"),
    ("Không chắc, nhưng có lẽ là xã Chợ Đồn", "correct"),
    # "theo tôi biết" prefaces an explanation, it does not hedge an answer
    ("Tôi không chắc chắn về thông tin này. Theo tôi biết, xã Ngọc Phái có thể được sáp nhập vào một đơn vị mới, nhưng tôi không nhớ chính xác tên.", "invalid"),
])
def test_hedged_commitment_after_any_abstention_phrase(pred, label):
    assert L(NP, pred)[0] == label, L(NP, pred)


@pytest.mark.parametrize("pred,label,detail", [
    # reasoning first, the answer alone on the last line (bold is stripped)
    ("Xã Mường Bám được sáp nhập vào xã Mường Bám mới? Theo Nghị quyết 2025... Tuy nhiên, tôi không chắc chắn.\n\nTôi không thể xác nhận chắc chắn; theo thông tin tôi nhớ nhất: **xã Vụ Bổn**.", "correct", "exact"),
    ("Xã Vụ Bổn (huyện Krông Pắc) được sáp nhập cùng xã Ea Kly... Không chắc chắn; theo phương án đã công bố, xã Vụ Bổn mới được thành lập.\n\n**Xã Vụ Bổn (tỉnh Đắk Lắk)**", "correct", "first_segment"),
    ("Tôi không chắc chắn về thông tin này. Theo Nghị quyết, tôi cho rằng xã Vụ Bổn được giữ nguyên, nhưng tôi không thể xác nhận chắc chắn.\n\n**Xã Vụ Bổn, tỉnh Đắk Lắk** (chưa kiểm chứng)", "correct", "first_segment"),
    ("Xã Vụ Bổn, huyện Krông Pắc, tỉnh Đắk Lắk: sau sắp xếp năm 2025, xã Vụ Bổn cùng thị trấn Phước An được hợp nhất.\n\nTôi không chắc chắn hoàn toàn, nhưng đáp án hợp lý nhất là:\n\n**Xã Ea Kly, tỉnh Đắk Lắk**", "other_wrong", None),
    ("Xã Vụ Bổn (huyện Krông Pắc) từ 01/7/2025 được đổi thành xã Ea Kly, tỉnh Đắk Lắk.\n\nCụ thể: Nghị quyết sắp xếp xã Vụ Bổn, xã Ea Kly thành xã mới tên là Ea Kly... Tuy nhiên, tôi không chắc chắn hoàn toàn.\n\n**Xã Ea Kly, tỉnh Đắk Lắk**", "other_wrong", None),
    ("Theo Nghị quyết..., xã Vụ Bổn cùng với xã Ea Kly... Tôi nhớ: xã Ea Kly mới gồm Ea Kly, Vụ Bổn... Tuy nhiên, xã Vụ Bổn được giữ nguyên.\n\nTrả lời: **xã Vụ Bổn, tỉnh Đắk Lắk**", "correct", "first_segment"),
    ("Xã Vụ Bổn không còn tồn tại; tôi không chắc chắn về đơn vị mới.\n\nNếu theo cơ cấu hiện hành mà tôi biết: **Xã Vụ Bổn**, huyện Krông Pắc, tỉnh Đắk Lắk.", "correct", "first_segment"),
    # not a committed last line: a list, an explanation, a question, a trailing-off name
    ("Xã Vụ Bổn được sáp nhập cùng các xã sau:\n\nXã Ea Kly\nXã Ea Kuăng\nXã Vụ Bổn", "correct", "contained"),
    ("Xã Vụ Bổn sáp nhập vào xã Ea Kly.\n\nLưu ý: thông tin có thể thay đổi.", "other_wrong", "relation"),
    ("Xã Vụ Bổn được sáp nhập vào xã Ea Kly.\n\nXã Ea Kuăng?", "other_wrong", "relation"),
    ("Xã Vụ Bổn được sáp nhập vào xã Ea Kly.\n\nXã Ea Kuăng... hãy xem lại.", "other_wrong", "relation"),
])
def test_answer_alone_on_the_last_line_after_an_explanation(pred, label, detail):
    assert L(VB, pred) == (label, detail), L(VB, pred)


def test_last_line_does_not_override_a_bare_first_line():
    assert L(VB, "Xã Vụ Bổn\n\nGiải thích: xã Vụ Bổn được giữ nguyên.\n\nTỉnh Đắk Lắk") == ("correct", "exact")
    assert L(VB, "Xã Vụ Bổn, tỉnh Đắk Lắk\n\nGiải thích: xã Vụ Bổn được giữ nguyên.\n\nXã Ea Kly") == ("correct", "first_segment")
    assert L(NP, "Xã Ngọc Phái\n\nTheo Nghị quyết, xã Ngọc Phái sáp nhập vào xã Chợ Đồn.\n\nXã Chợ Đồn") == ("outdated", "exact")


def test_last_line_address_for_t4_and_its_components():
    it = short("Xã Đại Đồng, Tỉnh Nghệ An", "Xã Thanh Phong, Huyện Thanh Chương, Tỉnh Nghệ An")
    it["meta"].update(gold_ward="Xã Đại Đồng", gold_province="Tỉnh Nghệ An", old_ward_name="Xã Thanh Phong",
                      old_province_name="Tỉnh Nghệ An")
    raw = "Địa chỉ cũ: Số 156, thôn 8, xã Thanh Phong, huyện Thanh Chương, tỉnh Nghệ An\n\nĐịa chỉ hiện nay: Xã Đại Đồng, tỉnh Nghệ An."
    r = score(it, raw)
    assert (r.label, r.match_detail) == ("correct", "address")
    assert r.components == {"ward": "correct", "province": "correct"}
    raw = "Xã Thanh Phong, huyện Thanh Chương, tỉnh Nghệ An\n\nĐịa chỉ mới: Xã Thanh Phong, tỉnh Nghệ An."
    assert L(it, raw)[0] == "outdated"


def test_first_sentence_naming_another_unit_is_the_answer():
    # a bare address first, then an explanation that echoes the old name
    assert L(NP, "Phường Hoành Bồ, tỉnh Quảng Ninh.\n\nTheo hiểu biết của tôi, xã Ngọc Phái được sáp nhập vào phường Hoành Bồ, nhưng bạn nên kiểm tra lại.")[0] == "other_wrong"
    assert L(NP, "Xã Bằng Phúc\n\nLưu ý: Tôi không chắc chắn. Tôi nhớ xã Ngọc Phái được sáp nhập với một số xã, nhưng không thể xác nhận tên đơn vị mới.") == ("other_wrong", None)
    # a list of names is not an answer to "which unit"
    assert L(NP, "Xã Bằng Phúc\nXã Chợ Đồn\nXã Yên Thịnh")[0] == "other_wrong"


def test_classification_after_a_prefix_is_not_a_unit_name():
    assert L(short("Thành phố Đà Nẵng"), "Thành phố Đà Nẵng là Thành Phố Trực Thuộc Trung Ương") == ("correct", "subject_segment")
    assert L(VB, "Xã Vụ Bổn là xã Loại I") == ("correct", "subject_segment")
    assert L(VB, "Xã Vụ Bổn là xã Cấp 2") == ("correct", "subject_segment")
    assert L(VB, "Xã Vụ Bổn là xã Ea Kly") == ("other_wrong", "relation")


def test_merger_clause_does_not_end_at_a_partner_named_thanh():
    assert L(VB, "Xã Vụ Bổn sáp nhập với xã Thành Công thành xã Ea Kly") == ("other_wrong", "relation")
    assert L(VB, "Xã Vụ Bổn sáp nhập với xã Thành Công thành xã Vụ Bổn mới")[0] == "correct"
    assert L(short("Xã Thành Công", "Xã Vụ Bổn"), "Xã Vụ Bổn sáp nhập với xã Ea Kly thành xã Thành Công")[0] == "correct"


def test_doi_thanh_is_a_relation_verb():
    it = short("Xã Quang Chiểu")
    assert L(it, "Xã Quang Chiểu được đổi thành xã Mường Chanh") == ("other_wrong", "relation")
    assert L(it, "Xã Quang Chiểu (huyện Mường Lát, Thanh Hóa) từ 01/7/2025 được đổi thành xã Mường Chanh, tỉnh Thanh Hóa.") == ("other_wrong", "relation")
    assert L(short("Xã Mường Chanh", "Xã Quang Chiểu"), "Xã Quang Chiểu được đổi thành xã Mường Chanh")[0] == "correct"


def test_cap_xa_followed_by_a_name_names_the_unit():
    it = short("Xã Sảng Mộc")
    assert L(it, "Xã Sảng Mộc thuộc đơn vị hành chính cấp xã Võ Nhai") == ("other_wrong", "relation")
    assert L(it, "Xã Sảng Mộc thuộc đơn vị hành chính cấp xã Võ Nhai, huyện Võ Nhai, tỉnh Thái Nguyên.") == ("other_wrong", "relation")
    assert L(it, "Xã Sảng Mộc thuộc đơn vị hành chính cấp xã") == ("correct", "subject_segment")
    assert L(it, "Xã Sảng Mộc thuộc đơn vị hành chính cấp xã mới") == ("correct", "subject_segment")
    assert L(it, "Xã Sảng Mộc thuộc đơn vị hành chính cấp xã Sảng Mộc") == ("correct", "relation")


def test_negated_relation_verb_names_no_answer():
    ch = ["Tỉnh Đồng Nai", "Tỉnh Bà Rịa - Vũng Tàu", "Tỉnh Lâm Đồng", "Thành phố Hồ Chí Minh"]
    assert extract_letter("Tỉnh Bà Rịa - Vũng Tàu vẫn là một tỉnh độc lập, không thuộc Thành phố Hồ Chí Minh", ch)[0] is None
    assert extract_letter("Tỉnh Bà Rịa - Vũng Tàu không còn tồn tại, nay thuộc Thành phố Hồ Chí Minh", ch)[0] == "D"
    it = short("Thành phố Hồ Chí Minh", "Tỉnh Bình Dương")
    assert L(it, "Phường Phú Cường không còn thuộc tỉnh Bình Dương, nay thuộc Thành phố Hồ Chí Minh") == ("correct", "relation")
    assert L(VB, "Xã Vụ Bổn không sáp nhập vào xã nào, vẫn là xã Vụ Bổn")[0] == "correct"


def test_enumerating_clause_in_an_abstention_names_no_answer():
    raw = ("Xã Vụ Bổn (huyện Krông Pắc) không tồn tại trong hệ thống hành chính mà tôi biết, nên tôi không thể xác nhận "
           "một đơn vị cấp xã cụ thể nào. Các xã hiện hành ở khu vực này là xã Ea Kly, xã Ea Kuăng, xã Vụ Bổn, xã Ea Phê. "
           "Vì thông tin không chắc chắn, tôi không muốn đưa ra đáp án sai.")
    assert L(VB, raw) == ("invalid", "abstain")
    assert L(VB, "Xã Vụ Bổn hiện thuộc xã Vụ Bổn mới, tỉnh Đắk Lắk. Tôi không chắc chắn về điều này.")[0] == "correct"


def test_stated_last_line_wins_over_an_echoed_first_line():
    it = short("Xã Thái Bình, Tỉnh Lạng Sơn", "Thị trấn Nông trường Thái Bình, Huyện Đình Lập, Tỉnh Lạng Sơn")
    raw = ("Thị trấn Nông trường Thái Bình, huyện Đình Lập, tỉnh Lạng Sơn.\n\nSau sắp xếp năm 2025, thị trấn Nông "
           "trường Thái Bình nhập vào xã Thái Bình.\n\n**Xã Thái Bình, tỉnh Lạng Sơn**")
    assert L(it, raw)[0] == "correct"
    it = short("Xã Krông Nô, Tỉnh Đắk Lắk")
    it["meta"]["old_address"] = "Xã Krông Nô, Huyện Lắk, Tỉnh Đắk Lắk"
    raw = ("Địa chỉ cũ: Số 80, thôn 11, xã Krông Nô, huyện Lắk, tỉnh Đắk Lắk\n\n"
           "Địa chỉ hiện nay: Số 80, thôn 11, xã Krông Nô, tỉnh Đắk Lắk.")
    assert L(it, raw)[0] == "correct"
    it = short("Xã Thuần Trung", "Xã Lạc Sơn")
    raw = ("Xã Lạc Sơn, tỉnh Nghệ An (sau sắp xếp năm 2025, xã Lạc Sơn cũ được sáp nhập vào xã Bạch Hà).\n\n"
           "Câu trả lời: **xã Bạch Hà, tỉnh Nghệ An**")
    assert L(it, raw)[0] == "other_wrong"
    # without a stated last line, an answer-form first line still decides
    assert L(short("Xã Co Mạ", "Xã Pá Lông"), "Xã Pá Lông.\n\nCó thể nay là xã Co Mạ.")[0] == "outdated"


def test_last_line_address_may_start_with_house_number_and_hamlet():
    it = short("Xã Hạ Lang, Tỉnh Cao Bằng", "Xã Thống Nhất, Huyện Hạ Lang, Tỉnh Cao Bằng")
    raw = ("Theo Nghị quyết số 1654/NQ-UBTVQH15, xã Hạ Lang mới được thành lập trên cơ sở sáp nhập thị trấn Thanh "
           "Nhật và các xã Thắng Lợi, Thống Nhất.\n\n**Số 9, thôn 3, xã Hạ Lang, tỉnh Cao Bằng**")
    assert L(it, raw)[0] == "correct"
    it = short("Xã Tân Trụ, Tỉnh Tây Ninh", "Xã Bình Trinh Đông, Huyện Tân Trụ, Tỉnh Long An")
    raw = ("Xã Bình Trinh Đông thuộc huyện Tân Trụ, Long An, sau sáp nhập đơn vị hành chính năm 2025 thành xã Tân Trụ, "
           "tỉnh Tây Ninh.\n\nĐịa chỉ mới: Số 178, ấp 4, xã Tân Trụ, tỉnh Tây Ninh.")
    assert L(it, raw)[0] == "correct"


def test_mcq_guessed_letter_is_read_and_refusal_is_invalid():
    ch = ["Xã Púng Bánh", "Xã Mường Lèo", "Xã Sốp Cộp", "Xã Mường Lầm"]
    raw = ("Tôi không chắc chắn về thông tin này.\n\nNếu buộc phải chọn, tôi đoán là **B**, nhưng đây chỉ là phỏng "
           "đoán chứ không dựa trên căn cứ xác thực.")
    assert extract_letter(raw, ch) == ("B", "guess")
    assert extract_letter("Nếu buộc phải chọn, đáp án khả dĩ nhất theo suy đoán là: **C**", ch) == ("C", "guess")
    assert extract_letter("Tôi không chắc. Nếu đoán, mình không muốn đưa ra đáp án sai.", ch)[0] is None
    ch = ["Tỉnh Hưng Yên", "Thành phố Hà Nội", "Tỉnh Hà Nam", "Tỉnh Ninh Bình"]
    raw = ("Câu hỏi này có vẻ không hợp lý: tỉnh Hà Nam là một đơn vị hành chính cấp tỉnh độc lập, nên câu hỏi không "
           "có đáp án đúng trong các lựa chọn. Vì vậy tôi không thể chọn một chữ cái chính xác.")
    assert extract_letter(raw, ch) == (None, "abstain")
    assert L(mcq(ch, "D", "C"), raw)[0] == "invalid"
    # an explicit letter still wins over a refusal phrase elsewhere
    assert extract_letter("Đáp án: D, dù tôi không thể chọn với độ chắc chắn tuyệt đối.", ch)[0] == "D"


def test_number_words_before_a_counting_noun():
    it = short("2", "3")
    assert L(it, "Hai cấp.")[0] == "correct"
    assert L(it, "Ba cấp: tỉnh, huyện, xã.")[0] == "outdated"
    assert L(short("34", "63"), "Ba mươi bốn tỉnh, thành phố")[0] == "correct"
    assert L(short("34", "63"), "Năm 2025 có 34 tỉnh, thành phố")[0] == "correct"
