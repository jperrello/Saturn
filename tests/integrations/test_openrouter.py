import os
from pathlib import Path

import httpx
import pytest


REPO = Path(__file__).resolve().parents[2]


live = pytest.mark.skipif(
    not os.environ.get("SATURN_INTEGRATION_LIVE")
    or not os.environ.get("OPENROUTER_PROVISIONING_KEY"),
    reason="set SATURN_INTEGRATION_LIVE=1 and OPENROUTER_PROVISIONING_KEY to enable live key-mint test",
)


def test_openrouter_static_profile_shipped():
    f = REPO / "saturn" / "services" / "openrouter.toml"
    assert f.exists()
    text = f.read_text()
    assert 'name = "openrouter"' in text
    assert 'api_type = "openai"' in text
    assert "https://openrouter.ai/api/v1" in text
    assert 'api_key_env = "OPENROUTER_API_KEY"' in text


def test_orbeacon_profile_shipped():
    f = REPO / "saturn" / "services" / "orbeacon.toml"
    assert f.exists()
    text = f.read_text()
    assert 'name = "orbeacon"' in text
    assert 'enabled = true' in text
    assert 'provider = "openrouter"' in text
    assert 'api_key_env = "OPENROUTER_PROVISIONING_KEY"' in text


def test_openrouter_provider_module_importable():
    import importlib
    mod = importlib.import_module("saturn.providers.openrouter")
    assert mod.endpoint == "https://openrouter.ai/api/v1/keys"
    assert mod.api_base == "https://openrouter.ai/api/v1"
    assert callable(mod.payload)
    assert callable(mod.parse)
    assert callable(mod.revoke)


def test_openrouter_payload_shape():
    from saturn.providers.openrouter import payload
    body = payload(300)
    assert body["name"].startswith("saturn-beacon-")
    assert "expires_at" in body
    assert body["expires_at"].endswith("Z")
    assert "limit" not in body


def test_openrouter_payload_with_budget():
    from saturn.providers.openrouter import payload
    body = payload(300, max_budget_usd=2.5)
    assert body["limit"] == 2.5


def test_openrouter_parse_extracts_key_and_hash():
    from saturn.providers.openrouter import parse
    key, handle = parse({"key": "sk-or-test", "data": {"hash": "abc123"}})
    assert key == "sk-or-test"
    assert handle == "abc123"


def test_openrouter_static_config_loadable():
    from saturn.config import load_service_config
    cfg = load_service_config("openrouter")
    assert cfg is not None
    assert cfg.api_type == "openai"
    assert cfg.upstream.base_url == "https://openrouter.ai/api/v1"


def test_orbeacon_config_loadable():
    from saturn.config import load_service_config
    cfg = load_service_config("orbeacon")
    assert cfg is not None
    assert cfg.beacon.enabled is True
    assert cfg.beacon.provider == "openrouter"


@live
def test_openrouter_mint_and_revoke_live():
    import requests
    from saturn.providers.openrouter import endpoint, payload, parse, revoke
    api_key = os.environ["OPENROUTER_PROVISIONING_KEY"]
    body = payload(120, max_budget_usd=0.01)
    r = requests.post(
        endpoint, json=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=15,
    )
    assert r.status_code == 200, f"mint failed: {r.status_code} {r.text}"
    key, handle = parse(r.json())
    assert key.startswith("sk-or-")
    try:
        models = httpx.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=15,
        )
        assert models.status_code == 200
    finally:
        revoke(api_key, endpoint, handle)
