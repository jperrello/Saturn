import os
from pathlib import Path

import httpx
import pytest


REPO = Path(__file__).resolve().parents[2]


live = pytest.mark.skipif(
    not os.environ.get("SATURN_INTEGRATION_LIVE")
    or not os.environ.get("DEEPINFRA_API_KEY"),
    reason="set SATURN_INTEGRATION_LIVE=1 and DEEPINFRA_API_KEY to enable live scoped-JWT test",
)


def test_deepinfra_profile_shipped():
    f = REPO / "saturn" / "services" / "deepinfra.toml"
    assert f.exists()
    text = f.read_text()
    assert 'name = "deepinfra"' in text
    assert 'api_type = "openai"' in text
    assert "https://api.deepinfra.com/v1/openai" in text
    assert 'api_key_env = "DEEPINFRA_API_KEY"' in text
    assert 'enabled = true' in text
    assert 'provider = "deepinfra"' in text


def test_deepinfra_provider_module_importable():
    import importlib
    mod = importlib.import_module("saturn.providers.deepinfra")
    assert mod.endpoint == "https://api.deepinfra.com/v1/scoped-jwt"
    assert mod.api_base == "https://api.deepinfra.com/v1/openai"
    assert callable(mod.payload)
    assert callable(mod.parse)
    assert callable(mod.revoke)


def test_deepinfra_payload_shape():
    from saturn.providers.deepinfra import payload
    body = payload(300)
    assert body["api_key_name"] == "auto"
    assert body["expires_delta"] == 300
    assert "max_budget_usd" not in body


def test_deepinfra_payload_with_budget():
    from saturn.providers.deepinfra import payload
    body = payload(300, max_budget_usd=1.5)
    assert body["max_budget_usd"] == 1.5


def test_deepinfra_parse_returns_token_twice():
    from saturn.providers.deepinfra import parse
    key, handle = parse({"token": "jwt-abc"})
    assert key == "jwt-abc"
    assert handle == "jwt-abc"


def test_deepinfra_revoke_no_handle_is_noop():
    from saturn.providers.deepinfra import revoke
    revoke("dummy-key", "https://api.deepinfra.com/v1/scoped-jwt", None)


def test_deepinfra_config_loadable():
    from saturn.config import load_service_config
    cfg = load_service_config("deepinfra")
    assert cfg is not None
    assert cfg.api_type == "openai"
    assert cfg.beacon.enabled is True
    assert cfg.beacon.provider == "deepinfra"


@live
def test_deepinfra_mint_and_revoke_live():
    import requests
    from saturn.providers.deepinfra import endpoint, payload, parse, revoke
    api_key = os.environ["DEEPINFRA_API_KEY"]
    body = payload(120, max_budget_usd=0.01)
    r = requests.post(
        endpoint, json=body,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=15,
    )
    assert r.status_code in (200, 201), f"mint failed: {r.status_code} {r.text}"
    key, handle = parse(r.json())
    assert key
    try:
        models = httpx.get(
            "https://api.deepinfra.com/v1/openai/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=15,
        )
        assert models.status_code == 200
    finally:
        revoke(api_key, endpoint, handle)
