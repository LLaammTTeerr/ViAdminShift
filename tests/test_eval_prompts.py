import os
from datetime import date
from pathlib import Path

import pytest

from viadmin.eval.prompts import (
    apply_chat_template,
    build_messages,
    fold_system,
    format_date,
    parse_condition,
)

MCQ = {"id": "q1", "format": "mcq", "question": "Xã Tân Uyên (cũ) nay thuộc tỉnh/thành phố nào?",
       "choices": ["Bình Dương", "Thành phố Hồ Chí Minh", "Đồng Nai", "Tây Ninh"], "answer": "B"}
SHORT = {"id": "q2", "format": "short", "question": "Phường Bến Nghé (Quận 1, TP.HCM cũ) nay là phường nào?",
         "choices": None, "answer": "Phường Sài Gòn"}
P_OLD = {"passage_id": "p_old", "title": "Bình Dương", "era": "old",
         "revision_timestamp": "2025-05-01T10:00:00Z", "text": "Bình Dương là một tỉnh. OLDTEXT"}
P_NEW = {"passage_id": "p_new", "title": "Thành phố Hồ Chí Minh", "era": "new",
         "revision_timestamp": "2025-08-20T10:00:00Z", "text": "TP.HCM sau sáp nhập. NEWTEXT"}


def test_parse_condition():
    c = parse_condition("rag_mixed+date+sysdate")
    assert c.base == "rag_mixed" and c.mitigations == {"date", "sysdate"}
    assert c.context_condition == "mixed"
    assert parse_condition("closed").context_condition == "none"
    assert parse_condition("rag_new").context_condition == "new"
    assert parse_condition("closed+sysdate").mitigations == {"sysdate"}
    for bad in ["foo", "rag_mixed+bar", "closed+date", "rag_mixed+date+date"]:
        with pytest.raises(ValueError):
            parse_condition(bad)


def test_closed_mcq():
    m = build_messages(MCQ, "closed")
    assert [x["role"] for x in m] == ["system", "user"]
    u = m[1]["content"]
    assert "A. Bình Dương\nB. Thành phố Hồ Chí Minh\nC. Đồng Nai\nD. Tây Ninh" in u
    assert "một chữ cái" in u
    assert "Tài liệu" not in u
    assert "Hôm nay" not in m[0]["content"]


def test_short_instruction():
    u = build_messages(SHORT, "closed")[1]["content"]
    assert "Chỉ trả lời bằng tên đầy đủ" in u and "kèm loại đơn vị" in u
    assert "A." not in u


def test_rag_order_and_dates():
    u = build_messages(MCQ, "rag_mixed", [P_NEW, P_OLD])[1]["content"]
    assert u.index("NEWTEXT") < u.index("OLDTEXT")  # stored order kept
    assert "cập nhật ngày" not in u

    u = build_messages(MCQ, "rag_mixed+date", [P_NEW, P_OLD])[1]["content"]
    assert "(cập nhật ngày 20/08/2025)" in u and "(cập nhật ngày 01/05/2025)" in u
    assert u.index("NEWTEXT") < u.index("OLDTEXT")
    assert "từ cũ nhất đến mới nhất" not in u

    u = build_messages(MCQ, "rag_mixed+recency", [P_NEW, P_OLD])[1]["content"]
    assert u.index("OLDTEXT") < u.index("NEWTEXT")  # oldest first, newest last
    assert "từ cũ nhất đến mới nhất" in u
    assert "cập nhật ngày" not in u
    assert u.index("[Tài liệu 1] Bình Dương") < u.index("[Tài liệu 2] Thành phố Hồ Chí Minh")


def test_sysdate_configurable():
    m = build_messages(MCQ, "rag_mixed+sysdate", [P_OLD, P_NEW])
    assert "Hôm nay là ngày 13/10/2026." in m[0]["content"]
    m = build_messages(MCQ, "closed+sysdate", today=date(2027, 1, 2))
    assert "Hôm nay là ngày 02/01/2027." in m[0]["content"]


def test_system_prompt_identical_across_conditions():
    base = build_messages(MCQ, "closed")[0]["content"]
    assert build_messages(MCQ, "rag_new", [P_NEW])[0]["content"] == base
    assert build_messages(MCQ, "rag_mixed+date", [P_NEW, P_OLD])[0]["content"] == base
    assert build_messages(MCQ, "rag_mixed+sysdate", [P_NEW, P_OLD])[0]["content"].startswith(base)


def test_rag_requires_passages():
    with pytest.raises(ValueError):
        build_messages(MCQ, "rag_new", [])


def test_format_date():
    assert format_date("2025-08-20T10:00:00Z") == "20/08/2025"
    assert format_date("2025-06-11T23:59:59+00:00") == "11/06/2025"
    assert format_date(None) == "không rõ"


def test_fold_system():
    m = fold_system([{"role": "system", "content": "S"}, {"role": "user", "content": "U"}])
    assert m == [{"role": "user", "content": "S\n\nU"}]


class _NoSystemTok:
    def apply_chat_template(self, messages, **kw):
        if messages[0]["role"] == "system":
            raise ValueError("System role not supported")
        return "|".join(m["content"] for m in messages)


def test_apply_chat_template_folds_system_on_error():
    out = apply_chat_template(_NoSystemTok(), [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}])
    assert out == "S\n\nU"


def _qwen_cached() -> bool:
    hub = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"
    return (hub / "models--Qwen--Qwen3-1.7B").exists()


@pytest.mark.skipif(not _qwen_cached(), reason="Qwen3-1.7B tokenizer not in HF cache")
def test_qwen3_template_thinking_disabled(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-1.7B")
    s = apply_chat_template(tok, build_messages(MCQ, "closed+sysdate"))
    assert s.rstrip().endswith("<think>\n\n</think>")
    assert "Hôm nay là ngày 13/10/2026." in s
    assert s.count("<|im_start|>system") == 1


def test_short_instruction_variants():
    num = {**SHORT, "question": "Có bao nhiêu tỉnh?", "answer": "34"}
    assert "một con số" in build_messages(num, "closed")[1]["content"]
    addr = {**SHORT, "qtype": "T4_address", "answer": "Phường Sài Gòn, Thành phố Hồ Chí Minh"}
    assert "địa chỉ mới" in build_messages(addr, "closed")[1]["content"]
    assert "kèm loại đơn vị" in build_messages(SHORT, "closed")[1]["content"]


def test_passage_fields():
    p = {**P_NEW, "admin_text": "ADMINTEXT phường Sài Gòn"}
    u = build_messages(MCQ, "rag_new", [p])[1]["content"]
    assert "NEWTEXT" in u and "ADMINTEXT" not in u
    u = build_messages(MCQ, "rag_new", [p], passage_fields=("text", "admin_text"))[1]["content"]
    assert u.index("NEWTEXT") < u.index("ADMINTEXT")
    u = build_messages(MCQ, "rag_new", [P_NEW], passage_fields=("text", "admin_text"))[1]["content"]
    assert "NEWTEXT" in u  # null/missing field skipped


def test_date_recency_require_timestamps():
    p = {**P_OLD, "revision_timestamp": None}
    for c in ("rag_mixed+date", "rag_mixed+recency"):
        with pytest.raises(ValueError):
            build_messages(MCQ, c, [P_NEW, p])
    build_messages(MCQ, "rag_mixed", [P_NEW, p])  # fine without mitigations


def test_recency_parses_timezones():
    a = {**P_OLD, "revision_timestamp": "2025-08-01T10:00:00+07:00"}  # 03:00Z
    b = {**P_NEW, "revision_timestamp": "2025-08-01T05:00:00Z"}
    u = build_messages(MCQ, "rag_mixed+recency", [b, a])[1]["content"]
    assert u.index("OLDTEXT") < u.index("NEWTEXT")
