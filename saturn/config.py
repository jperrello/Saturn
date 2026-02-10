import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib

SERVICES_DIR = Path.home() / ".saturn" / "services"
BUILTIN_SERVICES_DIR = Path(__file__).parent / "services"


"""
Service configuration is split into three sub-dataclasses, each owning a separate concern:

- UpstreamConfig: Where to forward requests (remote API base URL and env var for its key)
- ServerConfig: How to run the local HTTP server (port binding and optional custom module)
- BeaconConfig: API key rotation (temporary key distribution, expiration)

ServiceConfig composes all three. A single service definition (e.g. openrouter.toml) describes
the upstream target, the local server, and the beacon together. They're nested rather than
flattened because they're logically independent—you can have a service with no beacon (plain proxy),
no upstream (local Ollama), or a custom server module.
"""

@dataclass
class UpstreamConfig:
    base_url: str
    api_key_env: Optional[str] = None

@dataclass
class BeaconConfig:
    enabled: bool = False
    provider: Optional[str] = None
    rotation_interval: int = 300
    expiration_interval: int = 600


@dataclass
class ServerConfig:
    port: int = 0
    module: Optional[str] = None


@dataclass
class ServiceConfig:
    name: str
    deployment: str = "cloud"
    api_type: str = "openai"
    priority: int = 50
    upstream: UpstreamConfig = field(default_factory=lambda: UpstreamConfig(base_url=""))
    server: ServerConfig = field(default_factory=ServerConfig)
    beacon: BeaconConfig = field(default_factory=BeaconConfig)

    @classmethod
    def from_dict(cls, data: dict) -> "ServiceConfig":
        upstream_data = data.get("upstream", {})
        upstream = UpstreamConfig(
            base_url=upstream_data.get("base_url", ""),
            api_key_env=upstream_data.get("api_key_env"),
        )

        server_data = data.get("server", {})
        server = ServerConfig(
            port=server_data.get("port", 0),
            module=server_data.get("module"),
        )

        beacon_data = data.get("beacon", {})
        beacon = BeaconConfig(
            enabled=beacon_data.get("enabled", False),
            provider=beacon_data.get("provider"),
            rotation_interval=beacon_data.get("rotation_interval", 300),
            expiration_interval=beacon_data.get("expiration_interval", 600),
        )

        return cls(
            name=data.get("name", ""),
            deployment=data.get("deployment", "cloud"),
            api_type=data.get("api_type", "openai"),
            priority=data.get("priority", 50),
            upstream=upstream,
            server=server,
            beacon=beacon,
        )

    def validate(self) -> list[str]:
        errors = []
        if not self.name:
            errors.append("name is required")
        if self.deployment not in ("cloud", "local", "network"):
            errors.append(f"invalid deployment type: {self.deployment}")
        if self.api_type not in ("openai", "anthropic", "ollama"):
            errors.append(f"invalid api_type: {self.api_type}")
        if not 0 <= self.priority <= 100:
            errors.append(f"priority must be 0-100, got: {self.priority}")
        if not self.upstream.base_url and not self.beacon.enabled and not self.server.module:
            errors.append("upstream.base_url required when beacon not enabled and no custom module")
        if self.beacon.enabled and not self.beacon.provider:
            errors.append("beacon.provider is required when beacon is enabled")
        return errors


def ensure_services_dir() -> Path:
    SERVICES_DIR.mkdir(parents=True, exist_ok=True)
    return SERVICES_DIR


def load_service_config(name: str) -> Optional[ServiceConfig]:
    config_path = SERVICES_DIR / f"{name}.toml"
    if not config_path.exists():
        config_path = BUILTIN_SERVICES_DIR / f"{name}.toml"
        if not config_path.exists():
            return None

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    config = ServiceConfig.from_dict(data)
    if config.name and config.name != name:
        raise ValueError(
            f"Config name mismatch: file is '{name}.toml' but name field is '{config.name}'. "
            f"Rename the file or fix the name field."
        )
    config.name = name
    return config


def list_service_configs(include_builtin: bool = True) -> list[tuple[str, ServiceConfig, bool]]:
    configs = []
    seen = set()

    if SERVICES_DIR.exists():
        for path in sorted(SERVICES_DIR.glob("*.toml")):
            name = path.stem
            seen.add(name)
            try:
                config = load_service_config(name)
                if config:
                    configs.append((name, config, False))
            except Exception as e:
                print(f"Warning: failed to load {path}: {e}", file=sys.stderr)

    if include_builtin and BUILTIN_SERVICES_DIR.exists():
        for path in sorted(BUILTIN_SERVICES_DIR.glob("*.toml")):
            name = path.stem
            if name not in seen:
                try:
                    with open(path, "rb") as f:
                        data = tomllib.load(f)
                    config = ServiceConfig.from_dict(data)
                    configs.append((name, config, True))
                except Exception as e:
                    print(f"Warning: failed to load {path}: {e}", file=sys.stderr)

    return configs


def get_config_path(name: str) -> Path:
    return SERVICES_DIR / f"{name}.toml"


def config_exists(name: str) -> bool:
    return get_config_path(name).exists()


def cmd_config_delete(name: str, force: bool = False) -> int:
    import time
    from .runner import is_service_running, stop_service, remove_service_info

    config_path = get_config_path(name)
    builtin_path = BUILTIN_SERVICES_DIR / f"{name}.toml"

    if builtin_path.exists() and not config_path.exists():
        print(f"Cannot delete built-in service '{name}'", file=sys.stderr)
        print(f"Create a user override first with: saturn config new")
        return 1

    if not config_path.exists():
        print(f"Service '{name}' not found", file=sys.stderr)
        return 1

    if is_service_running(name):
        if force:
            print(f"Stopping running service '{name}'...")
            stop_service(name)
            for _ in range(10):
                time.sleep(0.5)
                if not is_service_running(name):
                    break
            remove_service_info(name)
        else:
            print(f"Service '{name}' is currently running", file=sys.stderr)
            print("Stop it first with: saturn stop {name}")
            print("Or use --force to stop and delete")
            return 1

    config_path.unlink()
    print(f"Deleted {config_path}")
    return 0


def ask(question: str, default: str = "") -> str:
    if default:
        result = input(f"{question} [{default}]: ").strip()
        return result if result else default
    return input(f"{question}: ").strip()


def choose(question: str, choices: list[str], default: int = 0) -> str:
    print(f"\n{question}")
    for i, choice in enumerate(choices):
        marker = ">" if i == default else " "
        print(f"  {marker} {i + 1}. {choice}")
    while True:
        answer = input(f"Choice [1-{len(choices)}]: ").strip()
        if not answer:
            return choices[default]
        try:
            idx = int(answer) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass
        print(f"Please enter 1-{len(choices)}")


def cmd_config_new() -> int:
    print("=" * 55)
    print("  Saturn Service Configuration Wizard")
    print("=" * 55)
    print()

    name = ask("Service name (e.g., myopenai, deepseek)")
    if not name:
        print("Name is required", file=sys.stderr)
        return 1

    if config_exists(name):
        print(f"Service '{name}' already exists", file=sys.stderr)
        print(f"'{name}' already exists. Delete it first with: saturn config delete {name}")
        return 1

    builtin = BUILTIN_SERVICES_DIR / f"{name}.toml"
    if builtin.exists():
        print(f"'{name}' is a built-in service. Pick a different name.", file=sys.stderr)
        return 1

    deployment = choose(
        "Deployment type",
        ["cloud - Remote API service (OpenRouter, OpenAI, etc.)",
         "local - Local service (Ollama, LM Studio)",
         "network - Shared network proxy"],
        default=0
    ).split(" - ")[0]

    base_url = ask("API base URL (e.g., https://openrouter.ai/api/v1)")
    if not base_url:
        print("Base URL is required", file=sys.stderr)
        return 1

    api_key_env = ask("Environment variable for API key (leave empty if none)")

    print()
    print("Mode selection:")
    print("  PROXY mode: Saturn keeps your API key server-side.")
    print("              Clients connect to Saturn, which proxies to the API.")
    print("              Best for: sharing access without exposing keys")
    print()
    print("  BEACON mode: Saturn broadcasts ephemeral keys via mDNS.")
    print("               Clients call the API directly with rotated keys.")
    print("               Best for: minimal latency, direct API access")
    print()

    mode = choose(
        "Select mode",
        ["proxy - Keep keys server-side (recommended)",
         "beacon - Broadcast ephemeral keys"],
        default=0
    ).split(" - ")[0]

    beacon_enabled = mode == "beacon"

    beacon_provider = ""
    rotation_interval = 300

    if beacon_enabled:
        print()
        print("Beacon configuration:")
        beacon_provider = ask("Provider name (e.g., deepinfra, openrouter)")
        rotation_str = ask("Key rotation interval in seconds", "300")
        try:
            rotation_interval = int(rotation_str)
        except ValueError:
            rotation_interval = 300

    priority_str = ask("Priority (lower = preferred, 0-100)", "50")
    try:
        priority = int(priority_str)
        priority = max(0, min(100, priority))
    except ValueError:
        priority = 50

    port_str = ask("Specific port (0 = auto-assign)", "0")
    try:
        port = int(port_str)
    except ValueError:
        port = 0

    ensure_services_dir()
    config_path = get_config_path(name)

    lines = [
        f'name = "{name}"',
        f'deployment = "{deployment}"',
        'api_type = "openai"',
        f'priority = {priority}',
        '',
        '[upstream]',
        f'base_url = "{base_url}"',
    ]
    if api_key_env:
        lines.append(f'api_key_env = "{api_key_env}"')

    lines.extend([
        '',
        '[server]',
        f'port = {port}',
        '',
        '[beacon]',
        f'enabled = {"true" if beacon_enabled else "false"}',
    ])

    if beacon_enabled:
        if beacon_provider:
            lines.append(f'provider = "{beacon_provider}"')
        lines.append(f'rotation_interval = {rotation_interval}')

    config_path.write_text('\n'.join(lines) + '\n')

    print()
    print("=" * 55)
    print(f"  Created: {config_path}")
    print("=" * 55)
    print()
    print("Next steps:")
    print(f"  saturn run {name}     # Start the service")
    print(f"  saturn config delete {name}  # Delete the config")
    print(f"  saturn config list          # List all services")

    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: saturn config <command> [args]")
        print()
        print("Commands:")
        print("  list              List all configured services")
        print("  new               Interactive wizard to create a new service")
        print("  delete <name>     Delete a user service configuration")
        return 1

    command = sys.argv[1]

    if command == "list":
        return cmd_config_list()
    if command == "new":
        return cmd_config_new()
    if command == "delete":
        if len(sys.argv) < 3:
            print("Usage: saturn config delete <name> [--force]", file=sys.stderr)
            return 1
        force = "--force" in sys.argv or "-f" in sys.argv
        return cmd_config_delete(sys.argv[2], force=force)
    print(f"Unknown config command: {command}", file=sys.stderr)
    print("Run 'saturn config' for usage", file=sys.stderr)
    return 1