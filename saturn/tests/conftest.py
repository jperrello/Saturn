import os
import shutil
import tempfile
import pytest
from saturn.discovery import SaturnService


@pytest.fixture
def service():
    return SaturnService(
        name="test-ollama",
        host="192.168.1.50",
        port=8080,
        deployment="network",
        api_type="openai",
        priority=10,
        models=["llama3.2", "mistral"],
        capabilities=["chat", "code"],
        context=8192,
        cost="free",
    )


@pytest.fixture
def beacon():
    return SaturnService(
        name="test-beacon",
        host="192.168.1.50",
        port=8090,
        deployment="cloud",
        api_type="openai",
        api_base="https://api.deepinfra.com/v1/openai",
        priority=50,
        ephemeral_key="sk-test-ephemeral-key-12345",
        features="ephemeral_auth",
        models=[],
        capabilities=["chat"],
        context=4096,
        cost="paid",
    )


@pytest.fixture
def services(service, beacon):
    high = SaturnService(
        name="high-priority",
        host="10.0.0.1",
        port=8080,
        priority=5,
        models=["gpt-4"],
        capabilities=["chat", "code", "vision"],
        context=128000,
        cost="paid",
    )
    free = SaturnService(
        name="free-service",
        host="10.0.0.2",
        port=8080,
        priority=20,
        models=["llama3.2"],
        capabilities=["chat", "code"],
        context=8192,
        cost="free",
    )
    return [service, beacon, high, free]


@pytest.fixture
def valid_config():
    from saturn.config import ServiceConfig, UpstreamConfig
    return ServiceConfig(
        name="test-service",
        deployment="cloud",
        api_type="openai",
        priority=50,
        upstream=UpstreamConfig(base_url="https://api.example.com/v1"),
    )


@pytest.fixture
def beacon_config():
    from saturn.config import ServiceConfig, UpstreamConfig, BeaconConfig
    return ServiceConfig(
        name="test-beacon",
        deployment="cloud",
        api_type="openai",
        priority=30,
        upstream=UpstreamConfig(
            base_url="https://api.deepinfra.com/v1/openai",
            api_key_env="DEEPINFRA_API_KEY",
        ),
        beacon=BeaconConfig(enabled=True, provider="deepinfra"),
    )


@pytest.fixture
def tmp_services_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("saturn.config.SERVICES_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def fallback_client():
    from fastapi.testclient import TestClient
    from saturn.servers.fallback import app
    return TestClient(app)
