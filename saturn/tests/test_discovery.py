import time
import socket
import threading
import uuid
import pytest
from zeroconf import Zeroconf, ServiceInfo
from saturn.discovery import SaturnDiscovery, SaturnAdvertiser


def unique_name():
    return f"test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def zc():
    z = Zeroconf(interfaces=["127.0.0.1"])
    yield z
    z.close()


def register(zc, name, port, props=None):
    stype = "_saturn._tcp.local."
    info = ServiceInfo(
        type_=stype,
        name=f"{name}.{stype}",
        port=port,
        addresses=[socket.inet_aton("127.0.0.1")],
        server=f"{name}.local.",
        properties=props or {
            "version": "1.0",
            "deployment": "network",
            "api_type": "openai",
            "priority": "10",
            "models": "llama3.2,mistral",
            "capabilities": "chat,code",
            "context": "8192",
            "cost": "free",
        },
    )
    zc.register_service(info)
    return info


@pytest.mark.slow
@pytest.mark.timeout(15)
def test_register_and_discover(zc):
    name = unique_name()
    register(zc, name, 9999)

    discovery = SaturnDiscovery()
    time.sleep(2.5)

    services = discovery.get_all_services()
    discovery.stop()

    found = [s for s in services if s.name == name]
    assert len(found) == 1
    assert found[0].port == 9999

    zc.unregister_all_services()


@pytest.mark.slow
@pytest.mark.timeout(15)
def test_txt_record_parsing(zc):
    name = unique_name()
    register(zc, name, 7777, {
        "version": "1.0",
        "deployment": "cloud",
        "api_type": "openai",
        "api_base": "https://api.example.com/v1",
        "priority": "25",
        "ephemeral_key": "sk-test-key",
        "features": "ephemeral_auth",
        "models": "",
        "capabilities": "chat",
        "context": "32000",
        "cost": "paid",
    })

    discovery = SaturnDiscovery()
    time.sleep(2.5)

    services = discovery.get_all_services()
    discovery.stop()

    found = [s for s in services if s.name == name]
    assert len(found) == 1
    svc = found[0]
    assert svc.deployment == "cloud"
    assert svc.api_base == "https://api.example.com/v1"
    assert svc.priority == 25
    assert svc.ephemeral_key == "sk-test-key"
    assert svc.context == 32000
    assert svc.cost == "paid"

    zc.unregister_all_services()


@pytest.mark.slow
@pytest.mark.timeout(15)
def test_service_removal(zc):
    name = unique_name()
    removed = []

    def on_change(action, svc):
        if action == "removed":
            removed.append(svc.name)

    info = register(zc, name, 8888)
    discovery = SaturnDiscovery(on_service_change=on_change)
    time.sleep(2.5)

    assert any(s.name == name for s in discovery.get_all_services())

    zc.unregister_service(info)
    time.sleep(2.5)

    assert not any(s.name == name for s in discovery.get_all_services())
    discovery.stop()


@pytest.mark.slow
@pytest.mark.timeout(15)
def test_get_best_service(zc):
    low = unique_name()
    high = unique_name()
    register(zc, low, 5555, {"priority": "5", "deployment": "network", "api_type": "openai"})
    register(zc, high, 5556, {"priority": "50", "deployment": "network", "api_type": "openai"})

    discovery = SaturnDiscovery()
    time.sleep(2.5)

    best = discovery.get_best_service()
    discovery.stop()

    assert best is not None
    assert best.name == low

    zc.unregister_all_services()


@pytest.mark.slow
@pytest.mark.timeout(15)
def test_on_service_change_callback(zc):
    added = []

    def on_change(action, svc):
        if action == "added":
            added.append(svc.name)

    discovery = SaturnDiscovery(on_service_change=on_change)
    name = unique_name()
    register(zc, name, 6666)
    time.sleep(2.5)

    discovery.stop()
    assert name in added

    zc.unregister_all_services()


@pytest.mark.slow
@pytest.mark.timeout(20)
def test_concurrent_registrations(zc):
    names = [unique_name() for _ in range(5)]
    discovery = SaturnDiscovery()

    for i, name in enumerate(names):
        register(zc, name, 7000 + i)

    time.sleep(3)

    services = discovery.get_all_services()
    discovery.stop()

    found = {s.name for s in services}
    for name in names:
        assert name in found, f"Missing: {name}"

    zc.unregister_all_services()


@pytest.mark.slow
@pytest.mark.timeout(20)
def test_advertiser_roundtrip():
    name = unique_name()
    adv = SaturnAdvertiser(
        name=name,
        port=4444,
        deployment="network",
        api_type="openai",
        priority=15,
        models=["test-model"],
        capabilities=["chat"],
    )
    adv.register()

    discovery = SaturnDiscovery()
    time.sleep(3)

    services = discovery.get_all_services()
    discovery.stop()
    adv.unregister()

    found = [s for s in services if name in s.name]
    assert len(found) >= 1


@pytest.mark.slow
@pytest.mark.timeout(15)
def test_advertiser_context_manager():
    name = unique_name()
    with SaturnAdvertiser(name=name, port=3333, priority=10) as adv:
        discovery = SaturnDiscovery()
        time.sleep(2.5)
        services = discovery.get_all_services()
        discovery.stop()
        found = [s for s in services if name in s.name]
        assert len(found) >= 1
