import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
RESEARCH = REPO / "dist" / "research" / "repos" / "hermes.md"


# Invariant 1 — NO built-in hermes.toml (saturn must not advertise hermes by default)
def test_no_builtin_hermes_profile():
    p = REPO / "saturn" / "services" / "hermes.toml"
    assert not p.exists(), (
        f"unexpected built-in {p} — Hermes ecosystem ships no OpenAI-compatible "
        f"inference server (see {RESEARCH}). Saturn must not advertise it by default."
    )


# Invariant 2 — research artifact exists and contains the negative finding
def test_research_finding_present():
    assert RESEARCH.exists(), f"missing {RESEARCH}"
    text = RESEARCH.read_text().lower()
    assert "no nousresearch repo ships an openai-compatible" in text or \
           "no openai-compat" in text, "research must record the negative finding"
    for kw in ("vllm", "llama.cpp", "ollama"):
        assert kw in text, f"research must recommend {kw} as alternative"


# Invariant 3 — `saturn run hermes` exits non-zero with a curated error citing the
# negative finding and the recommended wrapper path. Today saturn says only
# "Service 'hermes' not found" — that is NOT enough.
@pytest.mark.parametrize("name", ["hermes", "hermes-agent"])
def test_saturn_run_hermes_emits_curated_error(name):
    r = subprocess.run(
        [sys.executable, "-m", "saturn", "run", name],
        cwd=str(REPO), capture_output=True, text=True, timeout=15.0,
    )
    assert r.returncode != 0, f"expected non-zero exit, got {r.returncode}"
    blob = (r.stdout + r.stderr).lower()
    assert any(k in blob for k in ("vllm", "llama.cpp", "sglang", "ollama")), \
        f"error must recommend a wrapper. got stderr={r.stderr!r} stdout={r.stdout!r}"
    assert "nous" in blob or "hermes-agent" in blob or "openai-compat" in blob, \
        f"error must explain the Hermes ecosystem gap. got {blob!r}"


# Invariant 4 — `saturn hermes` shortcut also rejected with curated error
def test_saturn_hermes_shortcut_rejected():
    r = subprocess.run(
        [sys.executable, "-m", "saturn", "hermes"],
        cwd=str(REPO), capture_output=True, text=True, timeout=15.0,
    )
    assert r.returncode != 0
    blob = (r.stdout + r.stderr).lower()
    assert any(k in blob for k in ("vllm", "llama.cpp", "sglang", "ollama")), \
        f"shortcut must recommend a wrapper. got stderr={r.stderr!r}"


# Invariant 5 — saturn.providers.hermes is importable and signals unimplementable
# clearly via NotImplementedError when its primary entry is invoked. (We don't want
# a silent ModuleNotFoundError — we want a documented refusal.)
def test_provider_module_explicit_refusal():
    import importlib
    try:
        mod = importlib.import_module("saturn.providers.hermes")
    except ModuleNotFoundError as e:
        pytest.fail(
            f"saturn.providers.hermes must exist as a documented refusal stub, "
            f"not be missing. Today: {e}"
        )
    has_message = any(
        "vllm" in str(getattr(mod, attr, "")).lower() or
        "ollama" in str(getattr(mod, attr, "")).lower() or
        "nous" in str(getattr(mod, attr, "")).lower()
        for attr in dir(mod)
    )
    assert has_message, (
        f"saturn.providers.hermes must document the negative finding "
        f"(reference vLLM/llama.cpp/SGLang/Ollama or Nous weights). "
        f"attrs: {[a for a in dir(mod) if not a.startswith('_')]}"
    )


# Invariant 6 — discovery does not surface a hermes-kind service from saturn itself
def test_discover_does_not_advertise_hermes():
    from saturn.discovery import discover
    services = discover(timeout=2.0)
    bad = [s for s in services if "hermes" in s.name.lower()]
    assert not bad, (
        f"saturn must not advertise hermes by default, found: "
        f"{[(s.name, s.host, s.port) for s in bad]}"
    )
