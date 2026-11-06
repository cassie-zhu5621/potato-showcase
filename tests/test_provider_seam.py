"""The provider seam: adding one must not be able to change the one in use."""
import importlib
from pathlib import Path

import pytest
from planning import provider


def _fresh(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("NOTICEBOT_LLM_PROVIDER", raising=False)
    else:
        monkeypatch.setenv("NOTICEBOT_LLM_PROVIDER", value)
    provider._CACHE.clear()
    # Pin _ENV_LOADED so the developer's own .env cannot answer for these tests.
    # It genuinely can now: before provider.py read .env, this whole file passed
    # while the variable was inert, which is the opposite of a guarantee.
    monkeypatch.setattr(provider, "_ENV_LOADED", True)
    return provider


def test_unset_is_gemini(monkeypatch):
    # The guarantee the whole design rests on: a fresh clone, the other machine,
    # or a branch that never heard of this variable gets exactly what it had.
    p = _fresh(monkeypatch, None)
    assert p.provider_name() == "gemini"
    assert p._impl().__name__.endswith("gemini_provider")


@pytest.mark.parametrize("name", ["gemini", "google", "GEMINI", " gemini "])
def test_gemini_aliases(monkeypatch, name):
    assert _fresh(monkeypatch, name)._impl().__name__.endswith("gemini_provider")


@pytest.mark.parametrize("name", ["anthropic", "claude", "Anthropic"])
def test_anthropic_aliases(monkeypatch, name):
    assert _fresh(monkeypatch, name)._impl().__name__.endswith("anthropic_provider")


def test_unknown_provider_is_loud(monkeypatch):
    p = _fresh(monkeypatch, "gpt")
    with pytest.raises(RuntimeError, match="not a provider"):
        p._impl()


def test_both_expose_the_seam(monkeypatch):
    for name in ("gemini", "anthropic"):
        mod = _fresh(monkeypatch, name)._impl()
        for attr in ("call_json", "warm", "model_name", "DEFAULT_MODEL"):
            assert hasattr(mod, attr), f"{name} is missing {attr}"


def test_anthropic_drops_a_gemini_model_name(monkeypatch):
    # judge.py forwards NOTICEBOT_GEMINI_JUDGE_MODEL as `model`. Left alone that
    # is a Gemini name arriving at an Anthropic endpoint -- a 404 whose cause is
    # three files away.
    mod = _fresh(monkeypatch, "anthropic")._impl()
    assert mod.model_name("gemini-3.5-flash").startswith("claude")
    assert mod.model_name("claude-opus-5") == "claude-opus-5"


def test_dotenv_selects_the_provider_before_anything_imports_it(tmp_path, monkeypatch):
    """The bug this guards: .env is loaded inside call_json, but provider_name()
    runs earlier -- at planner.py import time. Before the fix, a .env saying
    'anthropic' selected gemini, and the file was silently doing nothing."""
    import subprocess, sys, os as _os
    root = Path(__file__).resolve().parents[1]
    env_file = root / ".env"
    backup = env_file.read_text() if env_file.exists() else None
    try:
        env_file.write_text("NOTICEBOT_LLM_PROVIDER=anthropic\n")
        env = {k: v for k, v in _os.environ.items()
               if k != "NOTICEBOT_LLM_PROVIDER"}
        env["PYTHONPATH"] = str(root)
        out = subprocess.run(
            [sys.executable, "-c",
             "from planning.provider import provider_name; print(provider_name())"],
            capture_output=True, text=True, cwd=str(root), env=env)
        assert out.stdout.strip() == "anthropic", out.stderr
    finally:
        if backup is None:
            env_file.unlink(missing_ok=True)
        else:
            env_file.write_text(backup)


def test_an_inline_variable_beats_the_dotenv_file(monkeypatch):
    """`NOTICEBOT_LLM_PROVIDER=gemini python3 ...` must win, so one run can be
    switched back without editing the file."""
    import planning.provider as p
    monkeypatch.setenv("NOTICEBOT_LLM_PROVIDER", "gemini")
    monkeypatch.setattr(p, "_ENV_LOADED", False)
    assert p.provider_name() == "gemini"


def test_38_flash_never_gets_minimal_thinking(monkeypatch):
    """gemini-3.8-flash rejects thinking_level=minimal with an error; .env said
    minimal for 3.5. The provider maps it rather than failing every call."""
    from planning import gemini_provider as g
    monkeypatch.setenv("NOTICEBOT_GEMINI_THINKING_LEVEL", "minimal")
    assert g.thinking_level("gemini-3.8-flash") == "low"
    assert g.thinking_level("gemini-3.6-flash") == "minimal"
    monkeypatch.setenv("NOTICEBOT_GEMINI_THINKING_LEVEL", "medium")
    assert g.thinking_level("gemini-3.8-flash") == "medium"


def test_a_thinking_model_gets_room_to_answer(monkeypatch):
    """Thoughts share max_output_tokens; a 768 cap was cut off mid-JSON on 3.8."""
    from planning import gemini_provider as g
    sent = {}

    class FakeClient:
        class interactions:
            @staticmethod
            def create(**kw):
                sent.update(kw)
                raise RuntimeError("stop here")

    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(g, "_client", lambda key: FakeClient)
    monkeypatch.setenv("NOTICEBOT_GEMINI_THINKING_LEVEL", "minimal")
    import pytest as _pt
    with _pt.raises(RuntimeError):
        g.call_json("p", {"type": "object"}, model="gemini-3.8-flash", max_output_tokens=768)
    assert sent["generation_config"]["thinking_level"] == "low"
    assert sent["generation_config"]["max_output_tokens"] >= g.THINKING_BUDGET_FLOOR
    with _pt.raises(RuntimeError):
        g.call_json("p", {"type": "object"}, model="gemini-3.6-flash", max_output_tokens=768)
    assert sent["generation_config"]["max_output_tokens"] == 768
