import json
import re

import pytest

from viadmin.eval import runner
from viadmin.eval.backends import FakeBackend
from viadmin.eval.metrics import aggregate, cell_key, consistency


def _w(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _meta(pc, wc, group=None, diac=True):
    return {"province_changed": pc, "ward_changed": wc, "change_type": "merged", "old_province_code": "74",
            "new_province_code": "79", "old_ward_code": None, "new_ward_code": None,
            "consistency_group": group, "has_diacritics": diac}


ITEMS = [
    {"id": "T6-1", "qtype": "T6_reverse", "question": "Tỉnh Bình Dương (cũ) nay thuộc tỉnh/thành phố nào?",
     "format": "short", "choices": None, "answer": "Thành phố Hồ Chí Minh", "answer_aliases": [],
     "old_answer": "Bình Dương", "meta": _meta(True, False, "g74")},
    {"id": "T1-1", "qtype": "T1_membership", "question": "Phường Phú Cường (cũ) nay thuộc tỉnh/thành phố nào?",
     "format": "mcq", "choices": ["Bình Dương", "Thành phố Hồ Chí Minh", "Đồng Nai", "Tây Ninh"],
     "answer": "B", "answer_aliases": [], "old_answer": "A", "meta": _meta(True, True, "g74")},
    {"id": "T1-2", "qtype": "T1_membership", "question": "Phường Hiệp Thành (cũ) nay thuộc tỉnh/thành phố nào?",
     "format": "mcq", "choices": ["Đồng Nai", "Bình Dương", "Thành phố Hồ Chí Minh", "Tây Ninh"],
     "answer": "C", "answer_aliases": [], "old_answer": "B", "meta": _meta(True, True, "g74")},
    {"id": "T1-3", "qtype": "T1_membership", "question": "Phường Tràng Tiền (cũ) nay thuộc tỉnh/thành phố nào?",
     "format": "short", "choices": None, "answer": "Hà Nội", "answer_aliases": [],
     "old_answer": "Hà Nội", "meta": _meta(False, True, None, diac=False)},
    {"id": "T0-1", "qtype": "T0_headline", "question": "Từ 1/7/2025 Việt Nam có bao nhiêu tỉnh, thành phố?",
     "format": "short", "choices": None, "answer": "34", "answer_aliases": ["34 tỉnh, thành phố"],
     "old_answer": "63", "meta": {"province_changed": None, "ward_changed": None, "consistency_group": None}},
]
PASSAGES = [
    {"passage_id": "w_old_74", "title": "Bình Dương", "entity_type": "province", "entity_code": "74", "era": "old",
     "revision_id": 1, "revision_timestamp": "2025-05-01T00:00:00Z", "text": "OLD Bình Dương là tỉnh."},
    {"passage_id": "w_new_79", "title": "Thành phố Hồ Chí Minh", "entity_type": "province", "entity_code": "79",
     "era": "new", "revision_id": 2, "revision_timestamp": "2025-08-01T00:00:00Z", "text": "NEW TP.HCM gồm Bình Dương."},
]
TEMPLATE_PASSAGES = [
    {"passage_id": "tpl_1", "title": "Hà Nội", "entity_type": "province", "entity_code": "01", "era": "new",
     "revision_id": None, "revision_timestamp": "2025-08-01T00:00:00Z", "text": "NEW Hà Nội."},
]


def _contexts():
    rows = []
    for it in ITEMS:
        pid_new = "tpl_1" if it["id"] == "T1-3" else "w_new_79"
        rows.append({"item_id": it["id"], "condition": "none", "passages": []})
        rows.append({"item_id": it["id"], "condition": "new", "passages": [pid_new]})
        rows.append({"item_id": it["id"], "condition": "mixed", "passages": [pid_new, "w_old_74"]})
    return rows


def oracle(messages):
    """Answers correctly when it sees NEW docs only, outdated if OLD doc is first, etc."""
    u = messages[-1]["content"]
    mcq = "A. " in u
    q = u
    first_doc = re.search(r"\n(OLD|NEW) ", u)
    if first_doc and first_doc.group(1) == "NEW":
        if mcq:
            return "Đáp án: " + ("B" if "Phú Cường" in q else "C")
        if "bao nhiêu" in q:
            return "34"
        return "Hà Nội" if "Tràng Tiền" in q else "TP.HCM"
    # closed / old-first: outdated
    if mcq:
        return "A" if "Phú Cường" in q else "(B)"
    if "bao nhiêu" in q:
        return "63 tỉnh thành"
    return "Hà Nội" if "Tràng Tiền" in q else "Bình Dương"


@pytest.fixture
def data(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    _w(d / "items.jsonl", ITEMS)
    _w(d / "contexts.jsonl", _contexts())
    _w(d / "passages.jsonl", PASSAGES)
    _w(d / "template_passages.jsonl", TEMPLATE_PASSAGES)
    return d


def _run(data, out, backend, conditions=("closed", "rag_new", "rag_mixed+recency")):
    return runner.run(
        backend, runner.read_jsonl(data / "items.jsonl"), list(conditions), out,
        contexts=runner.load_contexts(data / "contexts.jsonl"),
        passages=runner.load_passages([str(data / "passages.jsonl"), str(data / "template_passages.jsonl")]),
        batch_size=2, log=lambda s: None,
    )


def test_run_end_to_end(data, tmp_path):
    out = tmp_path / "res"
    be = FakeBackend(oracle, name="oracle")
    scores = _run(data, out, be)
    preds = runner.read_jsonl(out / "predictions.jsonl")
    assert len(preds) == len(ITEMS) * 3
    for p in preds:
        assert set(p) >= {"item_id", "condition", "model", "raw_output", "parsed", "label"}
        assert p["model"] == "oracle"
    by = {(p["item_id"], p["condition"]): p for p in preds}
    assert by[("T6-1", "closed")]["label"] == "outdated"
    assert by[("T6-1", "rag_new")]["label"] == "correct"
    assert by[("T1-2", "closed")]["label"] == "outdated"
    assert by[("T1-2", "rag_new")]["parsed"] == "C"
    assert by[("T1-3", "closed")]["label"] == "correct"  # old_answer == answer
    assert by[("T0-1", "closed")]["label"] == "outdated"  # "63 tỉnh thành" contains 63
    # recency puts OLD first -> oracle answers outdated
    assert by[("T6-1", "rag_mixed+recency")]["label"] == "outdated"

    s = scores["by_condition"]
    assert s["rag_new"]["all"]["accuracy"] == 1.0
    assert s["closed"]["all"]["labels"] == {"correct": 1, "outdated": 4, "other_wrong": 0, "invalid": 0}
    assert set(s["closed"]["by_qtype"]["T1_membership"]["cells"]) == {"pc1_wc1", "pc0_wc1"}
    assert set(s["closed"]["by_qtype"]["T0_headline"]["cells"]) == {"na"}
    assert s["closed"]["by_diacritics"]["without"]["n"] == 1
    c = s["rag_new"]["consistency"]
    assert c["n_groups"] == 1 and c["fully_consistent_rate"] == 1.0
    c = s["closed"]["consistency"]
    assert c["surface_acc"] == 0.0 and c["deep_acc_given_surface_wrong"] == 0.0
    assert json.loads((out / "scores.json").read_text())["n_predictions"] == 15
    cfg = json.loads((out / "run_config.json").read_text())
    assert cfg["prompt_version"] and cfg["backend"]["model"] == "oracle"


def test_resume_skips_done(data, tmp_path):
    out = tmp_path / "res"
    be = FakeBackend(oracle, name="oracle")
    _run(data, out, be, conditions=("closed",))
    n1 = len(runner.read_jsonl(out / "predictions.jsonl"))
    be2 = FakeBackend(oracle, name="oracle")
    _run(data, out, be2, conditions=("closed", "rag_new"))
    preds = runner.read_jsonl(out / "predictions.jsonl")
    assert n1 == 5 and len(preds) == 10
    assert len({(p["item_id"], p["condition"]) for p in preds}) == 10
    be3 = FakeBackend(oracle, name="oracle")
    _run(data, out, be3, conditions=("closed", "rag_new"))
    assert be3.calls == 0
    assert len(runner.read_jsonl(out / "predictions.jsonl")) == 10


def test_resume_refuses_other_model(data, tmp_path):
    out = tmp_path / "res"
    _run(data, out, FakeBackend(oracle, name="m1"), conditions=("closed",))
    with pytest.raises(SystemExit):
        _run(data, out, FakeBackend(oracle, name="m2"), conditions=("closed",))


def test_missing_passage_fails_before_generation(data, tmp_path):
    ctx = _contexts()
    ctx[1]["passages"] = ["does_not_exist"]
    _w(data / "contexts.jsonl", ctx)
    be = FakeBackend(oracle, name="oracle")
    with pytest.raises(KeyError):
        _run(data, tmp_path / "res", be, conditions=("rag_new",))
    assert be.calls == 0


def test_closed_needs_no_context_rows(data, tmp_path):
    _w(data / "contexts.jsonl", [])
    _run(data, tmp_path / "res", FakeBackend(oracle, name="o"), conditions=("closed", "closed+sysdate"))
    assert len(runner.read_jsonl(tmp_path / "res" / "predictions.jsonl")) == 10


def test_rescore(data, tmp_path):
    out = tmp_path / "res"
    _run(data, out, FakeBackend(oracle, name="oracle"), conditions=("closed",))
    rows = runner.read_jsonl(out / "predictions.jsonl")
    for r in rows:
        r["label"] = "invalid"
    _w(out / "predictions.jsonl", rows)
    s = runner.rescore(out, {it["id"]: it for it in ITEMS})
    assert s["by_condition"]["closed"]["all"]["labels"]["outdated"] == 4


def test_cli_with_fake(monkeypatch, data, tmp_path):
    import viadmin.eval.backends as B

    monkeypatch.setattr(B, "make_backend", lambda kind, model, **kw: FakeBackend(oracle, name=model))
    out = tmp_path / "cli"
    rc = runner.main([
        "--backend", "hf", "--model", "fake/model", "--items", str(data / "items.jsonl"),
        "--contexts", str(data / "contexts.jsonl"),
        "--passages", f"{data / 'passages.jsonl'},{data / 'template_passages.jsonl'}",
        "--conditions", "closed,rag_new,rag_mixed,rag_mixed+date,rag_mixed+recency,rag_mixed+sysdate",
        "--limit", "3", "--out", str(out),
    ])
    assert rc == 0
    preds = runner.read_jsonl(out / "predictions.jsonl")
    assert len(preds) == 3 * 6
    assert runner.main(["--items", str(data / "items.jsonl"), "--validate"]) == 0


def test_cell_key_and_empty_consistency():
    assert cell_key({"province_changed": True, "ward_changed": False}) == "pc1_wc0"
    assert cell_key({}) == "na"
    assert consistency([]) == {"n_groups": 0}
    assert aggregate([], {})["n_predictions"] == 0


def test_validate_rejects_short_t2_t3(tmp_path):
    from viadmin.eval.validate import lint_item
    it = {**ITEMS[0], "qtype": "T3_existence", "answer": "Không"}
    assert any("must be mcq" in e for e in lint_item(it))
    assert lint_item(ITEMS[0]) == []
