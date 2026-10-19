import json
import re
from pathlib import Path

from viadmin.eval import runner
from viadmin.eval.backends import FakeBackend
from viadmin.probe import build_items
from viadmin.probe.score_probe import (
    estimate_cutoff, grade, month_range, read_jsonl, score_group, strip_thousand_sep, text_plot,
)

ROOT = Path(__file__).resolve().parents[1]
ITEMS = ROOT / "data" / "probe" / "probe_items.jsonl"
HEAD = ROOT / "data" / "probe" / "headline_probe.jsonl"


def test_probe_files_match_builder_and_schema():
    items, head = read_jsonl(ITEMS), read_jsonl(HEAD)
    # committed files are exactly what the (seeded) builder produces
    assert items == build_items.build_probe_items()
    assert head == build_items.build_headline()
    assert read_jsonl(ROOT / "data" / "probe" / "probe_all.jsonl") == items + head
    ids = [it["id"] for it in items]
    assert len(ids) == len(set(ids))
    for it in items:
        for k in ("id", "month", "topic", "question", "choices", "answer", "source_url", "notes"):
            assert it[k], (it["id"], k)
        assert re.fullmatch(r"\d{4}-\d{2}", it["month"])
        assert it["topic"] in {"reform", "non_reform"}
        assert len(it["choices"]) == 4 and len(set(it["choices"])) == 4
        assert it["answer"] in "ABCD" and it["source_url"].startswith("https://")
        assert it["format"] == "mcq"
        if it["old_answer"] is not None:
            assert it["old_answer"] in it["choices"]
            assert it["choices"].index(it["old_answer"]) != "ABCD".index(it["answer"])
    anchors = [it for it in items if it["month"] < "2024-09"]
    assert len(anchors) == 6
    for m in month_range():
        assert sum(it["month"] == m and it["topic"] == "non_reform" for it in items) >= 3, m
    assert len(head) == 8 and all(h["format"] == "short" for h in head)


def test_cutoff_rule():
    ms = month_range()
    step = {m: ((3, 3) if m <= "2025-03" else (3, 0)) for m in ms}
    c = estimate_cutoff(step, anchor=(6, 6))
    assert (c["estimate"], c["lower"], c["upper"]) == ("2025-03", "2025-03", "2025-03")
    assert not c["right_censored"] and not c["weak_anchor"]
    # one isolated lucky month after the drop does not move the estimate, but widens the bracket
    lucky = dict(step, **{"2025-10": (3, 2)})
    c = estimate_cutoff(lucky, anchor=(6, 6))
    assert c["estimate"] == "2025-03" and c["upper"] == "2025-10"
    # a single early miss (dip) does not cut the estimate short
    dip = dict(step, **{"2024-11": (3, 1)})
    c = estimate_cutoff(dip, anchor=(6, 6))
    assert c["estimate"] == "2025-03" and c["lower"] == "2024-10"
    # everything known -> right-censored
    c = estimate_cutoff({m: (3, 3) for m in ms}, anchor=(6, 6))
    assert c["estimate"] == ms[-1] and c["right_censored"] and c["summary"].startswith(">=")
    # nothing known and anchors failed -> inconclusive
    c = estimate_cutoff({m: (3, 0) for m in ms}, anchor=(6, 2))
    assert c["none_pass"] and c["weak_anchor"] and c["estimate"] is None
    # bins with n < 2 are ignored
    c = estimate_cutoff(dict(step, **{"2026-03": (1, 1)}), anchor=(6, 6))
    assert c["estimate"] == "2025-03"


def test_thousand_separator_and_grading():
    assert strip_thousand_sep("Cả nước có 3.321 xã; trước đây 10,035.") == "Cả nước có 3321 xã; trước đây 10035."
    assert strip_thousand_sep("1.234.567 và 3.5") == "1234567 và 3.5"
    head = {h["id"]: h for h in read_jsonl(HEAD)}
    assert grade(head["headline-02"], "Cả nước có 3.321 đơn vị hành chính cấp xã.") == "correct"
    assert grade(head["headline-02"], "Có 10.035 xã, phường, thị trấn") == "outdated"
    assert grade(head["headline-01"], "63") == "outdated"
    assert grade(head["headline-04"], "TP.HCM") == "correct"


def test_end_to_end_with_runner(tmp_path):
    items = read_jsonl(ITEMS) + read_jsonl(HEAD)
    by_q = {it["question"]: it for it in items}

    def fake(messages):  # "knows" everything up to 2025-03, answers with the old structure after
        user = messages[-1]["content"]
        it = next(v for q, v in by_q.items() if q in user)
        if it["format"] == "short":
            old = it["old_answer"]
            return old[0] if isinstance(old, list) else old
        if it["month"] <= "2025-03":
            return f"Đáp án: {it['answer']}"
        wrong = next(L for L in "ABCD" if L != it["answer"])
        return wrong

    runner.run(FakeBackend(fake, name="fake-2025-03"), items, ["closed"], tmp_path)
    preds = read_jsonl(tmp_path / "predictions.jsonl")
    assert len(preds) == len(items)
    res = score_group(preds, {it["id"]: it for it in items})
    assert res["cutoff"]["estimate"] == "2025-03"
    assert res["by_month"]["anchor"]["accuracy"] == 1.0
    assert res["by_month"]["2025-04"]["accuracy"] == 0.0
    assert res["headline_outdated"] == 8 and res["headline_correct"] == 0
    plot = text_plot(res, "fake")
    assert "<- estimate" in plot and "effective cutoff: 2025-03" in plot
    json.dumps(res)  # serialisable
