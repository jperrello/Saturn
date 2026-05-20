import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
RESEARCH = REPO / "dist" / "research" / "hermes_client.md"


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _run(args, timeout=30.0, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run(
        [sys.executable, "-m", "saturn"] + args,
        cwd=str(REPO), capture_output=True, text=True, timeout=timeout, env=e,
    )


@pytest.fixture
def hermes_home():
    d = Path(tempfile.mkdtemp(prefix="hermes-home-"))
    yield d
    import shutil
    shutil.rmtree(d, ignore_errors=True)


def test_subcommand_exists():
    r = _run(["hermes-config", "--help"], timeout=10.0)
    assert r.returncode == 0, (
        f"`saturn hermes-config --help` exited {r.returncode}.\nstderr={r.stderr!r}"
    )
    blob = (r.stdout + r.stderr).lower()
    assert "hermes" in blob, f"help must mention Hermes: {blob!r}"


def test_snippet_default_renders_base_url(hermes_home):
    r = _run(
        ["hermes-config", "--base-url", "http://saturn.local:8080/v1"],
        timeout=10.0, env={"HERMES_HOME": str(hermes_home)},
    )
    assert r.returncode == 0, f"exit={r.returncode} stderr={r.stderr!r}"
    assert "http://saturn.local:8080/v1" in r.stdout, (
        f"snippet must echo --base-url. stdout={r.stdout!r}"
    )
    assert not (hermes_home / "config.yaml").exists(), (
        "default mode must not write config.yaml"
    )


def test_snippet_yaml_shape(hermes_home):
    r = _run(
        ["hermes-config", "--base-url", "http://x:1/v1"],
        timeout=10.0, env={"HERMES_HOME": str(hermes_home)},
    )
    assert r.returncode == 0
    assert "model:" in r.stdout, (
        f"snippet must be nested under 'model:'. stdout={r.stdout!r}"
    )
    assert ("provider: custom" in r.stdout) or ('provider: "custom"' in r.stdout), (
        f"snippet must set model.provider=custom. stdout={r.stdout!r}"
    )
    assert "base_url:" in r.stdout, (
        f"snippet must include model.base_url key. stdout={r.stdout!r}"
    )


def test_write_mode_creates_config(hermes_home):
    yaml = pytest.importorskip("yaml", reason="PyYAML not installed in test env")
    r = _run(
        ["hermes-config", "--base-url", "http://x:9999/v1", "--write"],
        timeout=10.0, env={"HERMES_HOME": str(hermes_home)},
    )
    assert r.returncode == 0, f"exit={r.returncode} stderr={r.stderr!r}"
    p = hermes_home / "config.yaml"
    assert p.exists(), f"--write must create {p}"
    data = yaml.safe_load(p.read_text())
    assert isinstance(data, dict), f"config.yaml must be a YAML mapping, got {type(data)}"
    assert data["model"]["provider"] == "custom"
    assert data["model"]["base_url"] == "http://x:9999/v1"


def test_write_mode_merges_existing(hermes_home):
    yaml = pytest.importorskip("yaml", reason="PyYAML not installed in test env")
    p = hermes_home / "config.yaml"
    p.write_text("logging:\n  level: debug\nmodel:\n  name: hermes-3\n")
    r = _run(
        ["hermes-config", "--base-url", "http://x:1/v1", "--write"],
        timeout=10.0, env={"HERMES_HOME": str(hermes_home)},
    )
    assert r.returncode == 0, f"exit={r.returncode} stderr={r.stderr!r}"
    data = yaml.safe_load(p.read_text())
    assert data["logging"]["level"] == "debug", "must preserve unrelated top-level keys"
    assert data["model"]["name"] == "hermes-3", "must preserve sibling keys under model"
    assert data["model"]["provider"] == "custom"
    assert data["model"]["base_url"] == "http://x:1/v1"


def test_hermes_home_override_respected(hermes_home):
    pytest.importorskip("yaml", reason="PyYAML not installed in test env")
    real_marker = Path.home() / ".hermes" / "config.yaml"
    pre_text = real_marker.read_text() if real_marker.exists() else None
    r = _run(
        ["hermes-config", "--base-url", "http://x:1/v1", "--write"],
        timeout=10.0, env={"HERMES_HOME": str(hermes_home)},
    )
    assert r.returncode == 0
    assert (hermes_home / "config.yaml").exists()
    if pre_text is None:
        assert not real_marker.exists(), (
            "must not write to real ~/.hermes when HERMES_HOME is set"
        )
    else:
        assert real_marker.read_text() == pre_text, (
            "must not modify real ~/.hermes/config.yaml when HERMES_HOME is set"
        )


def test_warns_bypass_paths(hermes_home):
    r = _run(
        ["hermes-config", "--base-url", "http://x:1/v1"],
        timeout=10.0, env={"HERMES_HOME": str(hermes_home)},
    )
    assert r.returncode == 0
    blob = r.stdout.lower()
    hits = sum(1 for kw in ("tts", "stt", "rl", "realtime") if kw in blob)
    assert hits >= 2, (
        f"snippet must warn that bypass paths (TTS/STT/RL/Realtime) won't route through Saturn. "
        f"hits={hits} stdout={r.stdout!r}"
    )
    assert "chat" in blob, "must clarify chat completions DO route through Saturn"


def test_documents_dummy_key(hermes_home):
    r = _run(
        ["hermes-config", "--base-url", "http://x:1/v1"],
        timeout=10.0, env={"HERMES_HOME": str(hermes_home)},
    )
    assert r.returncode == 0
    blob = r.stdout.lower()
    assert ("no-key-required" in blob) or ("dummy" in blob) or ("placeholder" in blob), (
        f"must document Hermes accepts a dummy key. stdout={r.stdout!r}"
    )


def test_does_not_recommend_openai_base_url(hermes_home):
    r = _run(
        ["hermes-config", "--base-url", "http://x:1/v1"],
        timeout=10.0, env={"HERMES_HOME": str(hermes_home)},
    )
    assert r.returncode == 0
    assert "OPENAI_BASE_URL" not in r.stdout, (
        "Saturn must NOT recommend OPENAI_BASE_URL — Hermes explicitly ignores it "
        "(runtime_provider.py:580). config.yaml is the only override path."
    )


def test_discovers_real_service(hermes_home):
    from saturn.discovery import SaturnAdvertiser
    port = _free_port()
    adv = SaturnAdvertiser(
        name=f"saturn-hermes-test-{port}",
        port=port,
        deployment="network",
        api_type="openai",
        api_base=f"http://127.0.0.1:{port}/v1",
        priority=10,
    )
    adv.register()
    time.sleep(1.0)
    try:
        r = _run(
            ["hermes-config", "--timeout", "4"],
            timeout=20.0, env={"HERMES_HOME": str(hermes_home)},
        )
        assert r.returncode == 0, f"exit={r.returncode} stderr={r.stderr!r}"
        assert f":{port}/v1" in r.stdout, (
            f"snippet must surface discovered :{port}/v1. stdout={r.stdout!r}"
        )
    finally:
        adv.unregister()


def test_client_module_importable():
    import importlib
    mod = importlib.import_module("saturn.clients.hermes")
    assert mod is not None


def test_doc_exists():
    p = REPO / "docs" / "integrations" / "hermes.md"
    assert p.exists(), f"missing {p}"
    blob = p.read_text().lower()
    for kw in ("config.yaml", "model.base_url", "hermes_home", "no-key-required", "tts", "stt"):
        assert kw in blob, f"docs/integrations/hermes.md must cover {kw!r}"
    assert "bypass" in blob, "docs must warn about bypass"
    assert "openai_base_url" in blob, (
        "docs must explain why OPENAI_BASE_URL is NOT used (Hermes skips it)"
    )


def test_research_finding_present():
    assert RESEARCH.exists(), f"missing {RESEARCH}"
