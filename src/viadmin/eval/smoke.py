"""GPU smoke test: load a model with the HF backend, answer 8 tiny Vietnamese MCQs.

  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \\
  uv run python -m viadmin.eval.smoke --model Qwen/Qwen3-1.7B --quant none

Prints JSON with load time, throughput (items/s), peak VRAM and the raw outputs.
The 8 questions are toy items for checking the pipeline only (not benchmark data).
"""

from __future__ import annotations

import argparse
import json
import time

from viadmin.eval.prompts import build_messages
from viadmin.eval.scorer import score

TOY = [
    ("Thủ đô của Việt Nam là thành phố nào?", ["Hà Nội", "Huế", "Đà Nẵng", "Cần Thơ"], "A"),
    ("Từ ngày 1/7/2025, Việt Nam có bao nhiêu tỉnh, thành phố trực thuộc trung ương?", ["63", "34", "28", "45"], "B"),
    ("Tỉnh Bình Dương được sáp nhập vào tỉnh/thành phố nào từ ngày 1/7/2025?",
     ["Đồng Nai", "Tây Ninh", "Thành phố Hồ Chí Minh", "Bình Phước"], "C"),
    ("Thành phố Hồ Chí Minh nằm ở miền nào của Việt Nam?", ["Miền Bắc", "Miền Trung", "Tây Nguyên", "Miền Nam"], "D"),
    ("Tỉnh Hà Giang được sáp nhập với tỉnh nào để thành tỉnh Tuyên Quang mới?",
     ["Tuyên Quang", "Lào Cai", "Cao Bằng", "Yên Bái"], "A"),
    ("Sông nào chảy qua Thủ đô Hà Nội?", ["Sông Hương", "Sông Hồng", "Sông Hàn", "Sông Sài Gòn"], "B"),
    ("Tỉnh Quảng Nam được sáp nhập vào đơn vị hành chính nào?",
     ["Quảng Ngãi", "Thừa Thiên Huế", "Thành phố Đà Nẵng", "Kon Tum"], "C"),
    ("Đặc khu Phú Quốc thuộc tỉnh nào sau sắp xếp năm 2025?", ["Cà Mau", "Kiên Giang", "Cần Thơ", "An Giang"], "D"),
]


def toy_items() -> list[dict]:
    return [
        {"id": f"toy{i}", "qtype": "T0_headline", "format": "mcq", "question": q, "choices": c,
         "answer": a, "answer_aliases": [], "old_answer": None, "meta": {}}
        for i, (q, c, a) in enumerate(TOY)
    ]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-1.7B")
    ap.add_argument("--quant", choices=["none", "4bit"], default="none")
    ap.add_argument("--dtype", default="bfloat16")
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--max-new-tokens", type=int, default=16)
    ap.add_argument("--repeats", type=int, default=3)
    a = ap.parse_args(argv)

    import torch

    from viadmin.eval.backends import HFBackend

    torch.cuda.reset_peak_memory_stats()
    t0 = time.time()
    be = HFBackend(a.model, quant=a.quant, dtype=a.dtype, batch_size=a.batch_size)
    load_s = time.time() - t0
    mem_after_load = torch.cuda.max_memory_allocated() / 2**20

    items = toy_items()
    msgs = [build_messages(it, "closed") for it in items]
    be.generate(msgs[:2], 4)  # warm-up
    torch.cuda.synchronize()
    times, outs = [], []
    for _ in range(a.repeats):
        t = time.time()
        outs = be.generate(msgs, a.max_new_tokens)
        torch.cuda.synchronize()
        times.append(time.time() - t)
    best = min(times)
    res = {
        "model": a.model, "quant": a.quant, "dtype": a.dtype, "batch_size": a.batch_size,
        "max_new_tokens": a.max_new_tokens, "load_s": round(load_s, 1),
        "items_per_s": round(len(items) / best, 2), "batch_times_s": [round(x, 3) for x in times],
        "peak_vram_MiB_after_load": round(mem_after_load), "peak_vram_MiB": round(torch.cuda.max_memory_allocated() / 2**20),
        "peak_reserved_MiB": round(torch.cuda.max_memory_reserved() / 2**20),
        "torch": torch.__version__, "gpu": torch.cuda.get_device_name(0),
        "outputs": [{"id": it["id"], "raw": o, "parsed": (r := score(it, o)).parsed, "label": r.label}
                    for it, o in zip(items, outs)],
    }
    res["toy_accuracy"] = sum(o["label"] == "correct" for o in res["outputs"]) / len(items)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
