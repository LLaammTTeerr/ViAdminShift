"""Vietnamese prompt templates.

Conditions are parsed as ``base[+mitigation]*``:

* base ``closed``   - no passages (contexts.jsonl condition "none"; may be absent)
* base ``rag_new``  - passages from contexts.jsonl condition "new"
* base ``rag_mixed``- passages from contexts.jsonl condition "mixed" (stored order)
* ``+date``    - each passage header shows its revision date "(cập nhật ngày dd/mm/yyyy)";
                 no extra instruction, order unchanged.
* ``+recency`` - passages re-sorted oldest -> newest by revision_timestamp (newest last,
                 i.e. closest to the question) and ONE sentence states the ordering; no
                 dates shown.
* ``+sysdate`` - the system prompt additionally states today's date (default 13/10/2026).

Mitigations are orthogonal and composable (e.g. ``rag_mixed+date+sysdate``).
Bump PROMPT_VERSION whenever any template string changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

PROMPT_VERSION = "v1"

BASES = {"closed": "none", "rag_new": "new", "rag_mixed": "mixed"}
MITIGATIONS = ("date", "recency", "sysdate")
DEFAULT_TODAY = date(2026, 10, 13)

SYSTEM_BASE = "Bạn là một trợ lý hữu ích. Hãy trả lời chính xác và ngắn gọn bằng tiếng Việt."
SYSDATE_TMPL = "Hôm nay là ngày {d}."

INSTR_MCQ = "Chỉ trả lời bằng một chữ cái (A, B, C hoặc D) tương ứng với đáp án đúng, không giải thích."
INSTR_SHORT = "Chỉ trả lời bằng tên đầy đủ của đơn vị hành chính được hỏi, kèm loại đơn vị (phường/xã/đặc khu hoặc tỉnh/thành phố), không giải thích."
INSTR_SHORT_NUMBER = "Chỉ trả lời bằng một con số, không giải thích."
INSTR_SHORT_ADDRESS = "Chỉ trả lời bằng địa chỉ mới (tên phường/xã/đặc khu, tỉnh/thành phố), không giải thích."


def short_instruction(item: dict) -> str:
    """Instruction for short answers. The *kind* of answer (number / address / name)
    is chosen from the gold format, which the question wording already reveals."""
    ans = str(item.get("answer") or "").strip()
    if ans.isdigit():
        return INSTR_SHORT_NUMBER
    if item.get("qtype") == "T4_address" or "," in ans:
        return INSTR_SHORT_ADDRESS
    return INSTR_SHORT

CTX_HEADER = "Dưới đây là một số tài liệu tham khảo:"
CTX_USE = "Hãy sử dụng các tài liệu trên để trả lời câu hỏi sau."
RECENCY_NOTE = "Các tài liệu được sắp xếp theo thời gian cập nhật, từ cũ nhất đến mới nhất (tài liệu cuối cùng là mới nhất)."
QUESTION_ONLY = "Hãy trả lời câu hỏi sau."


@dataclass(frozen=True)
class Condition:
    name: str
    base: str
    mitigations: frozenset[str] = field(default_factory=frozenset)

    @property
    def context_condition(self) -> str:
        return BASES[self.base]


def parse_condition(name: str) -> Condition:
    parts = [p.strip() for p in name.strip().split("+")]
    base, mits = parts[0], parts[1:]
    if base not in BASES:
        raise ValueError(f"unknown base condition {base!r} in {name!r}; expected one of {list(BASES)}")
    for m in mits:
        if m not in MITIGATIONS:
            raise ValueError(f"unknown mitigation {m!r} in {name!r}; expected one of {MITIGATIONS}")
    if base == "closed" and set(mits) & {"date", "recency"}:
        raise ValueError(f"{name!r}: date/recency need passages; use a rag_* base")
    if len(set(mits)) != len(mits):
        raise ValueError(f"duplicate mitigation in {name!r}")
    return Condition(name.strip(), base, frozenset(mits))


def _parse_ts(ts: str) -> datetime:
    d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def format_date(ts: str | None) -> str:
    """ISO timestamp ('2025-08-15T03:12:00Z') -> '15/08/2025'."""
    if not ts:
        return "không rõ"
    d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return d.strftime("%d/%m/%Y")


def format_choices(choices: list[str]) -> str:
    return "\n".join(f"{'ABCDEFGH'[i]}. {c}" for i, c in enumerate(choices))


def build_messages(
    item: dict,
    condition: Condition | str,
    passages: list[dict] | None = None,
    today: date = DEFAULT_TODAY,
    passage_fields: tuple[str, ...] = ("text",),
) -> list[dict[str, str]]:
    """Return chat messages [{role, content}, ...] for one (item, condition).

    ``passage_fields``: passage fields concatenated (blank line between, empty/null
    fields skipped) as the passage body, e.g. ("text", "admin_text").
    """
    cond = parse_condition(condition) if isinstance(condition, str) else condition
    passages = list(passages or [])

    system = SYSTEM_BASE
    if "sysdate" in cond.mitigations:
        system += " " + SYSDATE_TMPL.format(d=today.strftime("%d/%m/%Y"))

    parts: list[str] = []
    if cond.base != "closed":
        if not passages:
            raise ValueError(f"condition {cond.name} for item {item.get('id')} has no passages")
        if cond.mitigations & {"date", "recency"}:
            bad = [p.get("passage_id") for p in passages if not p.get("revision_timestamp")]
            if bad:
                raise ValueError(f"{cond.name}: passages without revision_timestamp: {bad}")
        if "recency" in cond.mitigations:
            passages.sort(key=lambda p: _parse_ts(p["revision_timestamp"]))
        blocks = []
        for i, p in enumerate(passages, 1):
            head = f"[Tài liệu {i}] {p.get('title', '')}".rstrip()
            if "date" in cond.mitigations:
                head += f" (cập nhật ngày {format_date(p.get('revision_timestamp'))})"
            body = "\n\n".join(str(p[f]).strip() for f in passage_fields if p.get(f))
            if not body:
                raise ValueError(f"passage {p.get('passage_id')} has no content in fields {passage_fields}")
            blocks.append(f"{head}\n{body}")
        parts.append(CTX_HEADER)
        parts.append("\n\n".join(blocks))
        if "recency" in cond.mitigations:
            parts.append(RECENCY_NOTE)
        parts.append(CTX_USE)
    else:
        parts.append(QUESTION_ONLY)

    q = f"Câu hỏi: {item['question'].strip()}"
    if item.get("format") == "mcq":
        q += "\n" + format_choices(item["choices"])
        instr = INSTR_MCQ if len(item["choices"]) == 4 else INSTR_MCQ.replace(
            "(A, B, C hoặc D)", "(" + ", ".join("ABCDEFGH"[: len(item["choices"])]) + ")"
        )
    else:
        instr = short_instruction(item)
    parts.append(q)
    parts.append(instr)

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def apply_chat_template(tokenizer, messages: list[dict], enable_thinking: bool = False) -> str:
    """Render messages with the tokenizer's chat template (generation prompt added).

    ``enable_thinking`` is always passed (Qwen3 uses it; other Jinja templates ignore
    unknown variables). Templates that reject a system role (e.g. Gemma) get the system
    text folded into the first user turn.
    """
    kw = dict(tokenize=False, add_generation_prompt=True, enable_thinking=enable_thinking)
    try:
        return tokenizer.apply_chat_template(messages, **kw)
    except Exception as e:  # jinja2 TemplateError: "System role not supported"
        if messages and messages[0]["role"] == "system" and "system" in str(e).lower():
            return tokenizer.apply_chat_template(fold_system(messages), **kw)
        raise


def fold_system(messages: list[dict]) -> list[dict]:
    if not messages or messages[0]["role"] != "system":
        return messages
    sys_text, rest = messages[0]["content"], [dict(m) for m in messages[1:]]
    if rest and rest[0]["role"] == "user":
        rest[0]["content"] = sys_text + "\n\n" + rest[0]["content"]
    else:
        rest.insert(0, {"role": "user", "content": sys_text})
    return rest
