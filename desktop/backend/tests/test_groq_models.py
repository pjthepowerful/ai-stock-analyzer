"""Guard against shipping a decommissioned Groq model ID.

Groq retired llama-3.3-70b-versatile and llama-3.1-8b-instant on 2026-08-16.
A stale ID doesn't fail loudly — most Groq calls in this codebase sit inside
try/except and degrade to silence, so the app keeps running while its AI
features quietly stop working. This is a static check over the source.
"""
import os
import pathlib
import re
import sys

# tests/ -> backend/ -> desktop/ -> repo root
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_BACKEND = os.path.join(_ROOT, "desktop", "backend")
sys.path.insert(0, _BACKEND)
import engine as _engine  # noqa: F401,E402  installs the streamlit shim for trading.py

DECOMMISSIONED = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "llama3-70b-8192",
    "llama3-8b-8192",
    "mixtral-8x7b-32768",
    "gemma-7b-it",
]

SOURCES = ["trading.py", "smallcap_pullback.py",
           "desktop/backend/server.py", "desktop/backend/engine.py"]


def _src(rel):
    return (pathlib.Path(_ROOT) / rel).read_text()


def test_no_decommissioned_model_is_passed_to_the_api():
    """Comments referencing the old names are fine; a model= argument is not."""
    offenders = []
    for rel in SOURCES:
        for i, line in enumerate(_src(rel).splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for dead in DECOMMISSIONED:
                if dead in line:
                    offenders.append(f"{rel}:{i} {stripped[:90]}")
    assert not offenders, "decommissioned model in live code:\n" + "\n".join(offenders)


def test_models_come_from_one_definition():
    t = _src("trading.py")
    assert 'GROQ_MODEL_PRIMARY = os.environ.get(' in t
    assert 'GROQ_MODEL_FAST = os.environ.get(' in t
    # No call site should hardcode a model string of its own.
    hardcoded = re.findall(r'model\s*=\s*"(?!.*GROQ)[a-z0-9][^"]*"', t)
    assert not hardcoded, f"hardcoded model IDs: {hardcoded}"


def test_constants_are_env_overridable():
    import importlib
    os.environ["GROQ_MODEL_PRIMARY"] = "test/override-model"
    try:
        import trading
        importlib.reload(trading)
        assert trading.GROQ_MODEL_PRIMARY == "test/override-model"
        assert trading.GROQ_MODELS[0] == "test/override-model"
    finally:
        os.environ.pop("GROQ_MODEL_PRIMARY", None)
        import trading
        importlib.reload(trading)


def test_fallback_chain_has_a_second_distinct_model():
    """The chain exists so a 429 on the big model drops to a different rate
    bucket. A chain of one model repeated would defeat that."""
    import trading
    assert len(set(trading.GROQ_MODELS)) >= 2


def test_reasoning_leakage_is_stripped():
    """GPT-OSS returns chain-of-thought in a separate field, but if any leaks
    into content it must not reach the user."""
    import trading

    class _R:
        def __init__(self, text):
            M = type("M", (), {"content": text})
            C = type("C", (), {"message": M()})
            self.choices = [C()]

    assert trading._groq_text(_R("<think>secret</think>Answer.")) == "Answer."
    assert trading._groq_text(_R("Plain answer.")) == "Plain answer."
    assert trading._groq_text(_R(None)) == ""


def main():
    tests = [(n, o) for n, o in sorted(globals().items())
             if n.startswith("test_") and callable(o)]
    print("groq model tests")
    failed = 0
    for name, fn in tests:
        try:
            fn(); print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1; print(f"  FAIL  {name}: {e}")
        except Exception as e:
            failed += 1; print(f"  ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
