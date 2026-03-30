import time
import uuid
import pytest
from unittest.mock import patch, MagicMock

from saturn.mdns.subtypes import ROLE_SUBTYPES, subtypes_for_role
from saturn.mdns.backend import AdvertiseSpec


# --- subtypes_for_role ---

def test_coordinator():
    assert subtypes_for_role("coordinator") == ["_coordinator"]


def test_worker():
    assert subtypes_for_role("worker") == ["_worker"]


def test_cloud():
    assert subtypes_for_role("cloud") == ["_cloud"]


def test_beacon():
    assert subtypes_for_role("beacon") == ["_beacon"]


def test_unknown_role():
    assert subtypes_for_role("unknown") == []


def test_empty_role():
    assert subtypes_for_role("") == []


def test_all_roles_covered():
    for role, sub in ROLE_SUBTYPES.items():
        assert subtypes_for_role(role) == [sub]


# --- SaturnAdvertiser role -> subtypes ---

def test_advertiser_coordinator_subtypes():
    from saturn.discovery import SaturnAdvertiser
    with patch("saturn.mdns.detect.backend") as mock_backend:
        mock_backend.return_value = MagicMock()
        adv = SaturnAdvertiser(name="test", port=8080, role="coordinator")
        assert adv._subtypes == ["_coordinator"]


def test_advertiser_no_role_no_subtypes():
    from saturn.discovery import SaturnAdvertiser
    with patch("saturn.mdns.detect.backend") as mock_backend:
        mock_backend.return_value = MagicMock()
        adv = SaturnAdvertiser(name="test", port=8080)
        assert adv._subtypes == []


def test_advertiser_passes_subtypes_to_spec():
    from saturn.discovery import SaturnAdvertiser
    from saturn.mdns.backend import AdvertiseSpec
    captured = []

    backend_mock = MagicMock()
    backend_mock.advertise.side_effect = lambda spec: captured.append(spec)

    with patch("saturn.mdns.detect.backend", return_value=backend_mock), \
         patch("saturn.discovery.get_lan_ip", return_value="127.0.0.1"):
        adv = SaturnAdvertiser(name="test", port=8080, role="worker")
        adv.register()

    assert len(captured) == 1
    assert captured[0].subtypes == ["_worker"]


# --- UserspaceBackend subtype registration ---

def test_userspace_registers_subtypes():
    from zeroconf import NonUniqueNameException
    from saturn.mdns.userspace import UserspaceBackend

    spec = AdvertiseSpec(name="test", port=8080, txt={"id": "abc"}, subtypes=["_coordinator"])

    registered = []

    with patch("saturn.mdns.userspace.Zeroconf") as MockZC, \
         patch("saturn.mdns.userspace.get_instance_name", return_value="test"), \
         patch("saturn.mdns.userspace.update_instance_name"), \
         patch("saturn.discovery.get_lan_ip", return_value="127.0.0.1"):

        zc = MockZC.return_value
        zc.register_service.side_effect = lambda info: registered.append(info)

        backend = UserspaceBackend()
        backend.advertise(spec)

    types = [r.type for r in registered]
    assert "_saturn._tcp.local." in types
    assert "_coordinator._sub._saturn._tcp.local." in types


def test_userspace_no_subtypes_single_registration():
    from saturn.mdns.userspace import UserspaceBackend

    spec = AdvertiseSpec(name="test", port=8080, txt={"id": "abc"}, subtypes=[])

    registered = []

    with patch("saturn.mdns.userspace.Zeroconf") as MockZC, \
         patch("saturn.mdns.userspace.get_instance_name", return_value="test"), \
         patch("saturn.mdns.userspace.update_instance_name"), \
         patch("saturn.discovery.get_lan_ip", return_value="127.0.0.1"):

        zc = MockZC.return_value
        zc.register_service.side_effect = lambda info: registered.append(info)

        backend = UserspaceBackend()
        backend.advertise(spec)

    assert len(registered) == 1


def test_userspace_withdraw_cleans_subtypes():
    from saturn.mdns.userspace import UserspaceBackend

    spec = AdvertiseSpec(name="test", port=8080, txt={"id": "abc"}, subtypes=["_worker"])

    with patch("saturn.mdns.userspace.Zeroconf") as MockZC, \
         patch("saturn.mdns.userspace.get_instance_name", return_value="test"), \
         patch("saturn.mdns.userspace.update_instance_name"), \
         patch("saturn.discovery.get_lan_ip", return_value="127.0.0.1"):

        zc = MockZC.return_value
        backend = UserspaceBackend()
        backend.advertise(spec)
        backend.withdraw()

    assert zc.unregister_service.call_count == 2  # main + subtype


# --- Integration: subtype browsing filters correctly ---

@pytest.mark.slow
@pytest.mark.timeout(30)
def test_subtype_browse_filters():
    from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
    from saturn.mdns.userspace import UserspaceBackend
    from saturn.mdns.backend import AdvertiseSpec

    coord_spec = AdvertiseSpec(
        name=f"coord-{uuid.uuid4().hex[:6]}",
        port=19100,
        txt={"id": str(uuid.uuid4()), "role": "coordinator"},
        subtypes=["_coordinator"],
    )
    worker_spec = AdvertiseSpec(
        name=f"worker-{uuid.uuid4().hex[:6]}",
        port=19101,
        txt={"id": str(uuid.uuid4()), "role": "worker"},
        subtypes=["_worker"],
    )

    coord_backend = UserspaceBackend()
    worker_backend = UserspaceBackend()
    coord_backend.advertise(coord_spec)
    worker_backend.advertise(worker_spec)

    found = []

    class L(ServiceListener):
        def add_service(self, zc, type_, name):
            found.append(name)
        def update_service(self, zc, type_, name): pass
        def remove_service(self, zc, type_, name): pass

    zc = Zeroconf()
    listener = L()
    browser = ServiceBrowser(zc, "_coordinator._sub._saturn._tcp.local.", listener)

    time.sleep(3)

    browser.cancel()
    zc.close()
    coord_backend.withdraw()
    coord_backend.close()
    worker_backend.withdraw()
    worker_backend.close()

    assert len(found) >= 1
    assert all("coord" in n or "_coordinator" in n for n in found)
    assert not any("worker" in n for n in found)
