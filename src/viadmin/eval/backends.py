"""Generation backends with a uniform interface.

    backend.generate(list_of_messages, max_new_tokens) -> list[str]

All backends decode greedily with thinking disabled. Heavy imports (torch,
transformers, vllm, openai) happen lazily inside constructors so unit tests never
touch CUDA.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Protocol

from viadmin.eval.prompts import apply_chat_template, fold_system


class Backend(Protocol):
    name: str
    last_truncated: list[bool]

    def generate(self, batch: list[list[dict]], max_new_tokens: int) -> list[str]: ...

    def info(self) -> dict: ...


# --------------------------------------------------------------------------- HF


class HFBackend:
    """transformers backend: batched greedy generation with left padding.

    quant: "none" (bf16/fp16) | "4bit" (bitsandbytes NF4, double quant, bf16 compute)
    """

    def __init__(
        self,
        model: str,
        quant: str = "none",
        dtype: str = "bfloat16",
        batch_size: int = 8,
        enable_thinking: bool = False,
        device_map: str | None = "cuda",
    ):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.name = model
        self.quant = quant
        self.batch_size = batch_size
        self.enable_thinking = enable_thinking
        self.last_truncated: list[bool] = []
        self._torch = torch
        torch_dtype = getattr(torch, dtype)
        self.dtype = dtype

        self.tok = AutoTokenizer.from_pretrained(model)
        self.tok.padding_side = "left"
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token

        kw: dict = {"dtype": torch_dtype}
        if device_map:
            kw["device_map"] = device_map
        if quant == "4bit":
            from transformers import BitsAndBytesConfig

            kw["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch_dtype,
            )
        elif quant != "none":
            raise ValueError(f"unknown quant {quant!r}")
        self.model = AutoModelForCausalLM.from_pretrained(model, **kw)
        self.model.eval()
        # Greedy: clear sampling params shipped in generation_config.json (Qwen3 has them)
        gc = self.model.generation_config
        gc.do_sample = False
        gc.temperature = None
        gc.top_p = None
        gc.top_k = None
        if gc.pad_token_id is None:
            gc.pad_token_id = self.tok.pad_token_id

    def render(self, messages: list[dict]) -> str:
        return apply_chat_template(self.tok, messages, enable_thinking=self.enable_thinking)

    def generate(self, batch: list[list[dict]], max_new_tokens: int) -> list[str]:
        torch = self._torch
        prompts = [self.render(m) for m in batch]
        order = sorted(range(len(prompts)), key=lambda i: len(prompts[i]))
        outs: list[str] = [""] * len(prompts)
        trunc: list[bool] = [False] * len(prompts)
        eos_ids = self.model.generation_config.eos_token_id
        eos_set = set(eos_ids if isinstance(eos_ids, list) else [eos_ids]) - {None}
        for s in range(0, len(order), self.batch_size):
            idx = order[s : s + self.batch_size]
            enc = self.tok(
                [prompts[i] for i in idx], return_tensors="pt", padding=True, add_special_tokens=False
            ).to(self.model.device)
            with torch.inference_mode():
                gen = self.model.generate(
                    **enc,
                    max_new_tokens=max_new_tokens,
                    do_sample=False,
                    pad_token_id=self.tok.pad_token_id,
                )
            new = gen[:, enc["input_ids"].shape[1] :]
            for j, i in enumerate(idx):
                row = new[j].tolist()
                outs[i] = self.tok.decode(row, skip_special_tokens=True)
                trunc[i] = len(row) >= max_new_tokens and not (eos_set & set(row))
        self.last_truncated = trunc
        return outs

    def info(self) -> dict:
        return {"backend": "hf", "model": self.name, "quant": self.quant, "dtype": self.dtype,
                "batch_size": self.batch_size, "enable_thinking": self.enable_thinking}


# --------------------------------------------------------------------------- vLLM


class VLLMBackend:
    def __init__(
        self,
        model: str,
        enable_thinking: bool = False,
        max_model_len: int = 4096,
        gpu_memory_utilization: float = 0.9,
        dtype: str = "auto",
        quantization: str | None = None,
        tensor_parallel_size: int = 1,
    ):
        from vllm import LLM, SamplingParams  # lazy: optional dependency

        self.name = model
        self.enable_thinking = enable_thinking
        self.last_truncated: list[bool] = []
        self._SamplingParams = SamplingParams
        self._cfg = dict(max_model_len=max_model_len, gpu_memory_utilization=gpu_memory_utilization,
                         dtype=dtype, quantization=quantization, tensor_parallel_size=tensor_parallel_size)
        self.llm = LLM(model=model, seed=13, **{k: v for k, v in self._cfg.items() if v is not None})

    def generate(self, batch: list[list[dict]], max_new_tokens: int) -> list[str]:
        sp = self._SamplingParams(temperature=0.0, max_tokens=max_new_tokens, seed=13)
        # LLM.chat applies the model's chat template itself (no double BOS); thinking is
        # disabled through chat_template_kwargs. Templates without a system role get the
        # system text folded into the first user turn.
        kw = dict(use_tqdm=False, chat_template_kwargs={"enable_thinking": self.enable_thinking})
        try:
            res = self.llm.chat(batch, sp, **kw)
        except Exception as e:
            if "system" not in str(e).lower():
                raise
            res = self.llm.chat([fold_system(m) for m in batch], sp, **kw)
        outs, trunc = [], []
        for r in res:
            o = r.outputs[0]
            outs.append(o.text)
            trunc.append(o.finish_reason == "length")
        self.last_truncated = trunc
        return outs

    def info(self) -> dict:
        return {"backend": "vllm", "model": self.name, "enable_thinking": self.enable_thinking, **self._cfg}


# --------------------------------------------------------------------------- OpenAI-compatible


class OpenAIBackend:
    """Any OpenAI-compatible chat endpoint.

    base_url: --base-url or $OPENAI_BASE_URL; key: $OPENAI_API_KEY (or the env var named
    by api_key_env). For vLLM/SGLang servers pass ``template_kwargs=True`` so
    ``chat_template_kwargs={"enable_thinking": false}`` is sent.
    """

    def __init__(
        self,
        model: str,
        base_url: str | None = None,
        api_key_env: str = "OPENAI_API_KEY",
        template_kwargs: bool = False,
        enable_thinking: bool = False,
        concurrency: int = 8,
        system_role: bool = True,
        max_retries: int = 5,
        extra_body: dict | None = None,
    ):
        from openai import OpenAI

        self.name = model
        self.last_truncated: list[bool] = []
        self.template_kwargs = template_kwargs
        self.enable_thinking = enable_thinking
        self.concurrency = concurrency
        self.system_role = system_role
        self.extra_body = extra_body or {}
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=os.environ.get(api_key_env, "EMPTY"),
            max_retries=max_retries,
            timeout=float(os.environ.get("OPENAI_TIMEOUT", "600")),  # seconds per request; a congested API can hang
        )
        # optional requests-per-minute cap shared by the worker threads (some API accounts allow only 20 rpm)
        self.rpm = float(os.environ.get("OPENAI_RPM", "0"))
        self._lock = threading.Lock()
        self._next = 0.0

    def _wait_turn(self) -> None:
        if not self.rpm:
            return
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next)
            self._next = start + 60.0 / self.rpm
        time.sleep(max(0.0, start - now))

    def _one(self, messages: list[dict], max_new_tokens: int) -> tuple[str, bool]:
        msgs = messages if self.system_role else fold_system(messages)
        kw: dict = dict(model=self.name, messages=msgs, max_tokens=max_new_tokens, temperature=0.0)
        body = dict(self.extra_body)
        if self.template_kwargs:
            body["chat_template_kwargs"] = {"enable_thinking": self.enable_thinking}
        if body:
            kw["extra_body"] = body
        for attempt in range(3):
            try:
                self._wait_turn()
                r = self.client.chat.completions.create(**kw)
                c = r.choices[0]
                return (c.message.content or ""), c.finish_reason == "length"
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        raise RuntimeError("unreachable")

    def generate(self, batch: list[list[dict]], max_new_tokens: int) -> list[str]:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=self.concurrency) as ex:
            res = list(ex.map(lambda m: self._one(m, max_new_tokens), batch))
        self.last_truncated = [t for _, t in res]
        return [o for o, _ in res]

    def info(self) -> dict:
        return {"backend": "openai", "model": self.name, "base_url": self.base_url,
                "template_kwargs": self.template_kwargs, "enable_thinking": self.enable_thinking,
                "extra_body": self.extra_body}


# --------------------------------------------------------------------------- fake (tests)


class FakeBackend:
    """Deterministic backend for tests: ``fn(messages) -> str``."""

    def __init__(self, fn, name: str = "fake"):
        self.fn = fn
        self.name = name
        self.calls = 0
        self.last_truncated: list[bool] = []

    def generate(self, batch: list[list[dict]], max_new_tokens: int) -> list[str]:
        self.calls += 1
        out = [self.fn(m) for m in batch]
        self.last_truncated = [False] * len(out)
        return out

    def info(self) -> dict:
        return {"backend": "fake", "model": self.name}


def make_backend(kind: str, model: str, **kw) -> Backend:
    if kind == "hf":
        return HFBackend(model, **kw)
    if kind == "vllm":
        return VLLMBackend(model, **kw)
    if kind == "openai":
        return OpenAIBackend(model, **kw)
    raise ValueError(f"unknown backend {kind!r}")
