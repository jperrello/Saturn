import pytest
from saturn.providers import load


def test_load_deepinfra():
    mod = load("deepinfra")
    assert hasattr(mod, "endpoint")
    assert hasattr(mod, "api_base")
    assert hasattr(mod, "payload")
    assert hasattr(mod, "parse")
    assert hasattr(mod, "revoke")


def test_load_openrouter():
    mod = load("openrouter")
    assert hasattr(mod, "endpoint")
    assert hasattr(mod, "api_base")
    assert hasattr(mod, "payload")
    assert hasattr(mod, "parse")
    assert hasattr(mod, "revoke")


def test_load_nonexistent():
    with pytest.raises(ValueError, match="Unknown beacon provider"):
        load("nonexistent_provider_xyz")


def test_deepinfra_payload():
    mod = load("deepinfra")
    p = mod.payload(600)
    assert "api_key_name" in p
    assert p["expires_delta"] == 600


def test_openrouter_payload():
    mod = load("openrouter")
    p = mod.payload(600)
    assert "name" in p
    assert "saturn-beacon" in p["name"]
    assert "expires_at" in p
    assert p["expires_at"].endswith("Z")
