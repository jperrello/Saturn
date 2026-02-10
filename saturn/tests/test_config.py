import pytest
from saturn.config import (
    ServiceConfig,
    UpstreamConfig,
    BeaconConfig,
    ServerConfig,
    load_service_config,
    list_service_configs,
)


def test_from_dict_minimal():
    cfg = ServiceConfig.from_dict({"name": "test"})
    assert cfg.name == "test"
    assert cfg.deployment == "cloud"
    assert cfg.priority == 50
    assert cfg.upstream.base_url == ""
    assert cfg.beacon.enabled is False


def test_from_dict_full():
    cfg = ServiceConfig.from_dict({
        "name": "full",
        "deployment": "network",
        "api_type": "ollama",
        "priority": 10,
        "upstream": {"base_url": "http://localhost:11434", "api_key_env": "KEY"},
        "server": {"port": 9090, "module": "my.module"},
        "beacon": {
            "enabled": True,
            "provider": "deepinfra",
            "rotation_interval": 120,
            "expiration_interval": 300,
        },
    })
    assert cfg.name == "full"
    assert cfg.deployment == "network"
    assert cfg.api_type == "ollama"
    assert cfg.priority == 10
    assert cfg.upstream.base_url == "http://localhost:11434"
    assert cfg.upstream.api_key_env == "KEY"
    assert cfg.server.port == 9090
    assert cfg.server.module == "my.module"
    assert cfg.beacon.enabled is True
    assert cfg.beacon.provider == "deepinfra"
    assert cfg.beacon.rotation_interval == 120


def test_from_dict_partial():
    cfg = ServiceConfig.from_dict({"name": "partial", "upstream": {"base_url": "http://x"}})
    assert cfg.upstream.base_url == "http://x"
    assert cfg.upstream.api_key_env is None
    assert cfg.server.port == 0
    assert cfg.beacon.enabled is False


def test_validate_empty_name():
    cfg = ServiceConfig(name="")
    errors = cfg.validate()
    assert any("name" in e for e in errors)


def test_validate_bad_deployment():
    cfg = ServiceConfig(name="x", deployment="invalid")
    errors = cfg.validate()
    assert any("deployment" in e for e in errors)


def test_validate_bad_api_type():
    cfg = ServiceConfig(name="x", api_type="graphql")
    errors = cfg.validate()
    assert any("api_type" in e for e in errors)


def test_validate_priority_out_of_range():
    cfg = ServiceConfig(name="x", priority=200)
    errors = cfg.validate()
    assert any("priority" in e for e in errors)

    cfg2 = ServiceConfig(name="x", priority=-1)
    assert any("priority" in e for e in cfg2.validate())


def test_validate_missing_base_url():
    cfg = ServiceConfig(
        name="x",
        upstream=UpstreamConfig(base_url=""),
        beacon=BeaconConfig(enabled=False),
        server=ServerConfig(module=None),
    )
    errors = cfg.validate()
    assert any("base_url" in e for e in errors)


def test_validate_beacon_without_provider():
    cfg = ServiceConfig(
        name="x",
        beacon=BeaconConfig(enabled=True, provider=None),
        upstream=UpstreamConfig(base_url="http://x"),
    )
    errors = cfg.validate()
    assert any("provider" in e for e in errors)


def test_validate_beacon_with_provider():
    cfg = ServiceConfig(
        name="x",
        beacon=BeaconConfig(enabled=True, provider="deepinfra"),
        upstream=UpstreamConfig(base_url="http://x"),
    )
    assert cfg.validate() == []


def test_validate_custom_module_bypasses_base_url():
    cfg = ServiceConfig(
        name="x",
        upstream=UpstreamConfig(base_url=""),
        server=ServerConfig(module="saturn.servers.fallback"),
    )
    assert cfg.validate() == []


def test_validate_valid(valid_config):
    assert valid_config.validate() == []


def test_load_builtin_fallback():
    cfg = load_service_config("fallback")
    assert cfg is not None
    assert cfg.name == "fallback"
    assert cfg.server.module == "saturn.servers.fallback"


def test_load_nonexistent():
    assert load_service_config("nonexistent_service_xyz") is None


def test_list_includes_builtins():
    configs = list_service_configs(include_builtin=True)
    names = [name for name, _, _ in configs]
    assert "fallback" in names


def test_load_from_user_dir(tmp_services_dir):
    toml = 'name = "custom"\ndeployment = "cloud"\napi_type = "openai"\npriority = 25\n\n[upstream]\nbase_url = "http://custom.api"\n'
    (tmp_services_dir / "custom.toml").write_text(toml)
    cfg = load_service_config("custom")
    assert cfg is not None
    assert cfg.name == "custom"
    assert cfg.priority == 25
