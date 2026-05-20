import argparse
import os
import sys
from pathlib import Path


SNIPPET = """\
# Hermes ({hermes_home}/config.yaml)
#
# Saturn endpoint: {base_url}
#
# Paste under your existing top-level keys, OR run:
#     saturn hermes-config --base-url {base_url} --write
# to merge automatically (preserves sibling keys).

model:
  provider: custom
  base_url: {base_url}
  # Hermes accepts any non-empty string here; 'no-key-required' is the
  # documented placeholder. Saturn does not validate it locally.
  api_key: no-key-required

# Bypass paths (will NOT route through Saturn — they hardcode OpenAI/OpenRouter):
#   - TTS (text-to-speech)
#   - STT (speech-to-text)
#   - RL training loops (atropos / hindsight memory)
#   - Realtime voice
# Only chat completions traffic flows through Saturn via this override.
#
# NOTE: hermes-agent ignores OpenAI base-url environment variables
# (hermes_cli/runtime_provider.py:580). config.yaml under model.base_url
# is the single source of truth for the override — do not bother
# exporting an OpenAI-base-url env var; it has no effect.
"""


def render(base_url: str, hermes_home: Path) -> str:
    return SNIPPET.format(base_url=base_url, hermes_home=hermes_home)


def _hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    return Path.home() / ".hermes"


def _discover(timeout: float):
    from saturn.discovery import discover
    services = discover(timeout=timeout)
    openai = [s for s in services if s.api_type == "openai"]
    if not openai:
        return None
    openai.sort(key=lambda s: s.priority)
    return openai[0]


def _merge(home: Path, base_url: str) -> None:
    import yaml

    home.mkdir(parents=True, exist_ok=True)
    cfg = home / "config.yaml"
    data = {}
    if cfg.exists():
        loaded = yaml.safe_load(cfg.read_text())
        if isinstance(loaded, dict):
            data = loaded
    model = data.get("model")
    if not isinstance(model, dict):
        model = {}
    model["provider"] = "custom"
    model["base_url"] = base_url
    data["model"] = model
    cfg.write_text(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="saturn hermes-config",
        description="Emit or merge a Hermes (NousResearch hermes-agent) config.yaml snippet pointing at a Saturn endpoint.",
    )
    p.add_argument("--base-url", default=None, help="Saturn /v1 endpoint URL (skip discovery).")
    p.add_argument("--timeout", type=float, default=5.0, help="Discovery timeout seconds (default 5.0).")
    p.add_argument("--write", action="store_true", help=f"Merge into $HERMES_HOME/config.yaml (default {Path.home() / '.hermes' / 'config.yaml'}).")
    args = p.parse_args(argv)

    if args.base_url:
        base_url = args.base_url
    else:
        svc = _discover(args.timeout)
        if svc is None:
            print(
                "saturn hermes-config: no Saturn openai service found on the LAN.\n"
                "Hint: run `saturn endpoint` to verify discovery, or pass --base-url <url>.",
                file=sys.stderr,
            )
            return 1
        base_url = svc.effective_endpoint

    home = _hermes_home()
    sys.stdout.write(render(base_url, home))

    if args.write:
        try:
            _merge(home, base_url)
        except ImportError:
            print("saturn hermes-config: --write requires PyYAML (pip install pyyaml)", file=sys.stderr)
            return 2
        print(f"\n# wrote {home / 'config.yaml'}", flush=True)
    return 0
