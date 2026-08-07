"""Unit tests for the shared LLM layer (no network required)."""

from llm_client import _load_dotenv, _post_with_retry, ask_llm
import llm_client


class _FakeResponse:
    def __init__(self, data, ok=True, status=200):
        self._data = data
        self.ok = ok
        self.status_code = status

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._data


class _FakeRequests:
    class RequestException(Exception):
        pass

    def __init__(self, handler):
        self._handler = handler

    def post(self, *args, **kwargs):
        return self._handler(*args, **kwargs)


def test_ask_llm_dispatch_deepseek(monkeypatch):
    monkeypatch.setattr(llm_client, "PROVIDER", "deepseek")
    calls = {}

    def fake_deepseek(prompt):
        calls["prompt"] = prompt
        return "deepseek-answer"

    monkeypatch.setattr(llm_client, "_ask_deepseek", fake_deepseek)
    assert ask_llm("hi") == "deepseek-answer"
    assert calls["prompt"] == "hi"


def test_ask_llm_dispatch_local(monkeypatch):
    monkeypatch.setattr(llm_client, "PROVIDER", "local")
    calls = {}

    def fake_local(prompt):
        calls["prompt"] = prompt
        return "local-answer"

    monkeypatch.setattr(llm_client, "_ask_local", fake_local)
    assert ask_llm("hi") == "local-answer"
    assert calls["prompt"] == "hi"


def test_post_with_retry_extracts_completions(monkeypatch):
    monkeypatch.setattr(llm_client, "requests", _FakeRequests(
        lambda *a, **k: _FakeResponse({"choices": [{"text": "  hello  "}]})
    ))
    out = _post_with_retry("http://x", {"prompt": "p"}, lambda d: d["choices"][0]["text"].strip(), "src")
    assert out == "hello"


def test_post_with_retry_retries_then_raises(monkeypatch):
    monkeypatch.setattr(llm_client, "MAX_RETRIES", 2)

    def boom(*a, **k):
        raise _FakeRequests.RequestException("refused")

    monkeypatch.setattr(llm_client, "requests", _FakeRequests(boom))
    try:
        _post_with_retry("http://x", {}, lambda d: d, "src")
    except RuntimeError as err:
        assert "unavailable after 3 attempts" in str(err)
    else:
        raise AssertionError("expected RuntimeError")


def test_load_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / "test.env"
    env_file.write_text(
        "# comment\nKEY_ONE=value1\nKEY_TWO=\"quoted value\"\nKEY_ONE=ignored\n"
    )
    monkeypatch.setattr(llm_client.os, "environ", {})
    _load_dotenv(env_file)
    assert llm_client.os.environ["KEY_ONE"] == "value1"
    assert llm_client.os.environ["KEY_TWO"] == "quoted value"
