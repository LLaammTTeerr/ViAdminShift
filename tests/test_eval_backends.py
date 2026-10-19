from types import SimpleNamespace

from viadmin.eval.backends import FakeBackend, OpenAIBackend


def test_fake_backend():
    be = FakeBackend(lambda m: m[-1]["content"][::-1])
    assert be.generate([[{"role": "user", "content": "abc"}]], 4) == ["cba"]
    assert be.last_truncated == [False]


def test_openai_backend_with_mock(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    be = OpenAIBackend("my-model", base_url="http://127.0.0.1:9/v1", template_kwargs=True, system_role=False)
    seen = []

    def create(**kw):
        seen.append(kw)
        fin = "length" if "LONG" in kw["messages"][-1]["content"] else "stop"
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="B"), finish_reason=fin)])

    monkeypatch.setattr(be.client.chat.completions, "create", create)
    batch = [
        [{"role": "system", "content": "S"}, {"role": "user", "content": "Q1"}],
        [{"role": "system", "content": "S"}, {"role": "user", "content": "LONG"}],
    ]
    assert be.generate(batch, 8) == ["B", "B"]
    assert be.last_truncated == [False, True]
    kw = seen[0]
    assert kw["temperature"] == 0.0 and kw["max_tokens"] == 8 and kw["model"] == "my-model"
    assert kw["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
    assert all(m["role"] != "system" for m in kw["messages"])  # folded
    assert be.info()["backend"] == "openai"
