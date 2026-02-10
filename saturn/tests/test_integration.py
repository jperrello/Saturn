import time
import uuid
import pytest
from fastapi.testclient import TestClient
from saturn.discovery import SaturnDiscovery, SaturnAdvertiser, SaturnService, select_best_service
from saturn.servers.fallback import app as fallback_app


def unique_name():
    return f"integ-{uuid.uuid4().hex[:8]}"


@pytest.mark.slow
@pytest.mark.timeout(20)
def test_discover_select_respond():
    name = unique_name()
    adv = SaturnAdvertiser(
        name=name,
        port=18080,
        deployment="network",
        api_type="openai",
        priority=10,
        models=["dont_pick_me"],
        capabilities=["chat"],
    )
    adv.register()

    discovery = SaturnDiscovery()
    time.sleep(3)

    services = discovery.get_all_services()
    best = select_best_service(services, needs=["chat"])

    discovery.stop()
    adv.unregister()

    assert best is not None

    client = TestClient(fallback_app)
    r = client.post("/v1/chat/completions", json={
        "model": "dont_pick_me",
        "messages": [{"role": "user", "content": "test"}],
    })
    assert r.status_code == 200
    assert r.json()["choices"][0]["message"]["content"]


@pytest.mark.slow
@pytest.mark.timeout(20)
def test_priority_routing():
    low_name = unique_name()
    high_name = unique_name()

    low = SaturnAdvertiser(name=low_name, port=18081, priority=5, capabilities=["chat"])
    high = SaturnAdvertiser(name=high_name, port=18082, priority=50, capabilities=["chat"])

    low.register()
    high.register()

    discovery = SaturnDiscovery()
    time.sleep(3)

    services = discovery.get_all_services()
    best = select_best_service(services, needs=["chat"], prefer_free=False)

    discovery.stop()
    low.unregister()
    high.unregister()

    assert best is not None
    assert low_name in best.name


@pytest.mark.slow
@pytest.mark.timeout(20)
def test_capability_routing():
    vision_name = unique_name()
    chat_name = unique_name()

    vision = SaturnAdvertiser(
        name=vision_name, port=18083, priority=50,
        capabilities=["chat", "vision"],
    )
    chat = SaturnAdvertiser(
        name=chat_name, port=18084, priority=10,
        capabilities=["chat"],
    )

    vision.register()
    chat.register()

    discovery = SaturnDiscovery()
    time.sleep(3)

    services = discovery.get_all_services()
    best = select_best_service(services, needs=["vision"], prefer_free=False)

    discovery.stop()
    vision.unregister()
    chat.unregister()

    assert best is not None
    assert vision_name in best.name
