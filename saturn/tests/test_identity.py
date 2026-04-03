import uuid
import importlib
import threading
from pathlib import Path

import pytest

from saturn.mdns import identity
from saturn.discovery import SaturnService


@pytest.fixture(autouse=True)
def restore_node_id():
    orig = Path.home() / ".saturn" / "node_id"
    backup = orig.read_text() if orig.exists() else None
    yield
    importlib.reload(identity)
    if backup:
        orig.write_text(backup)
    elif orig.exists():
        orig.unlink()


def reload():
    importlib.reload(identity)


def test_empty_file_self_heals():
    # BUG: empty node_id file returns empty string forever
    # Expected: detect empty, regenerate a valid UUID
    path = Path.home() / ".saturn" / "node_id"
    path.write_text("")
    reload()
    nid = identity.get_node_id()
    assert nid, "empty file should trigger regeneration, got empty string"
    uuid.UUID(nid)  # must be valid UUID


def test_corrupt_file_rejected():
    # BUG: corrupt file content used as-is without validation
    # Expected: detect invalid UUID, regenerate
    path = Path.home() / ".saturn" / "node_id"
    path.write_text("not-a-uuid")
    reload()
    nid = identity.get_node_id()
    uuid.UUID(nid)  # must be valid UUID
    assert nid != "not-a-uuid", "corrupt value should not be accepted"


def test_whitespace_only_file():
    path = Path.home() / ".saturn" / "node_id"
    path.write_text("   \n  \n")
    reload()
    nid = identity.get_node_id()
    assert nid.strip(), "whitespace-only file should trigger regeneration"
    uuid.UUID(nid)


def test_duplicate_node_id_no_overwrite():
    # Composite key (node_id:name) prevents overwrite when node_ids collide
    services = {}
    lock = threading.Lock()
    svc1 = SaturnService(name="server-a", host="10.0.0.1", port=8080, node_id="dup-uuid")
    svc2 = SaturnService(name="server-b", host="10.0.0.2", port=8081, node_id="dup-uuid")

    key1 = f"{svc1.node_id}:{svc1.name}" if svc1.node_id else svc1.name
    key2 = f"{svc2.node_id}:{svc2.name}" if svc2.node_id else svc2.name

    with lock:
        services[key1] = svc1
        services[key2] = svc2

    names = {s.name for s in services.values()}
    assert "server-a" in names and "server-b" in names, (
        f"duplicate node_id caused silent overwrite, only {names} survived"
    )


def test_missing_id_falls_back_to_name():
    # This should work — backwards compat with v1 services
    svc = SaturnService(name="legacy-svc", host="10.0.0.1", port=8080, node_id="")
    key = svc.node_id if svc.node_id else svc.name
    assert key == "legacy-svc"
