"""T4 per-component (ward / province) scoring added for the generator's address items."""

from __future__ import annotations

from viadmin.eval.metrics import stats
from viadmin.eval.scorer import score, score_address_components

ITEM = {
    "id": "T4-x", "qtype": "T4_address", "format": "short", "choices": None,
    "answer": "Phường Bình Cơ, Thành phố Hồ Chí Minh", "answer_aliases": [],
    "old_answer": "Xã Bình Mỹ, Huyện Bắc Tân Uyên, Tỉnh Bình Dương",
    "meta": {"province_changed": True, "ward_changed": True, "has_diacritics": True,
             "gold_ward": "Phường Bình Cơ", "gold_province": "Thành phố Hồ Chí Minh",
             "old_ward_name": "Xã Bình Mỹ", "old_district_name": "Huyện Bắc Tân Uyên",
             "old_province_name": "Tỉnh Bình Dương"},
}


def comp(raw, item=ITEM):
    return score_address_components(item, raw)


def test_full_and_street_prefix():
    assert comp("Phường Bình Cơ, Thành phố Hồ Chí Minh") == {"ward": "correct", "province": "correct"}
    assert comp("Địa chỉ mới: Số 5, thôn 2, Phường Bình Cơ, TP.HCM, Việt Nam") == {"ward": "correct", "province": "correct"}


def test_mixed_old_new():
    assert comp("Phường Bình Cơ, Tỉnh Bình Dương") == {"ward": "correct", "province": "outdated"}
    assert comp("Xã Bình Mỹ, Thành phố Hồ Chí Minh") == {"ward": "outdated", "province": "correct"}
    assert comp("Xã Bình Mỹ, Huyện Bắc Tân Uyên, Tỉnh Bình Dương") == {"ward": "outdated", "province": "outdated"}


def test_partial_relation_abstain():
    assert comp("Phường Bình Cơ") == {"ward": "correct", "province": "other_wrong"}
    assert comp("Xã Bình Mỹ, Huyện Bắc Tân Uyên, Tỉnh Bình Dương nay là Phường Bình Cơ, Thành phố Hồ Chí Minh") == \
        {"ward": "correct", "province": "correct"}
    assert comp("Tôi không biết") == {"ward": "invalid", "province": "invalid"}
    assert comp("Phường Tân Định, Thành phố Hà Nội") == {"ward": "other_wrong", "province": "other_wrong"}


def test_nodiac_twin_and_no_components_elsewhere():
    nd = dict(ITEM, meta=dict(ITEM["meta"], has_diacritics=False))
    assert comp("Phuong Binh Co, Thanh pho Ho Chi Minh", nd) == {"ward": "correct", "province": "correct"}
    assert comp("Phuong Binh Co, Thanh pho Ho Chi Minh") == {"ward": "other_wrong", "province": "other_wrong"}
    short = {"id": "s", "format": "short", "answer": "Phường Sài Gòn", "answer_aliases": [], "old_answer": None, "meta": {}}
    assert score(short, "Phường Sài Gòn").components is None


def test_score_carries_components_and_metrics_aggregate():
    r = score(ITEM, "Phường Bình Cơ, Tỉnh Bình Dương")
    assert r.label == "other_wrong" and r.components == {"ward": "correct", "province": "outdated"}
    rows = [{"label": "other_wrong", "components": r.components, "format": "short"},
            {"label": "correct", "components": {"ward": "correct", "province": "correct"}, "format": "short"}]
    s = stats(rows)
    assert s["components"]["ward"]["accuracy"] == 1.0
    assert s["components"]["province"]["outdated_rate"] == 0.5
    assert s["components"]["both_correct_rate"] == 0.5
    assert "components" not in stats([{"label": "correct", "format": "mcq"}])
