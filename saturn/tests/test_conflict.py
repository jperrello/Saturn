import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path
import tempfile
import os

from saturn.mdns.conflict import get_instance_name, update_instance_name, next_name


# --- next_name ---

def test_next_name_base():
    assert next_name("Saturn") == "Saturn (2)"


def test_next_name_increments():
    assert next_name("Saturn (2)") == "Saturn (3)"
    assert next_name("Saturn (9)") == "Saturn (10)"


def test_next_name_preserves_spaces():
    assert next_name("My Saturn Node") == "My Saturn Node (2)"


# --- get_instance_name / update_instance_name ---

def test_get_instance_name_returns_base_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr("saturn.mdns.conflict._NAME_FILE", tmp_path / "instance_name")
    assert get_instance_name("MySaturn") == "MySaturn"


def test_get_instance_name_reads_saved(tmp_path, monkeypatch):
    f = tmp_path / "instance_name"
    f.write_text("MySaturn (2)")
    monkeypatch.setattr("saturn.mdns.conflict._NAME_FILE", f)
    assert get_instance_name("MySaturn") == "MySaturn (2)"


def test_update_instance_name_persists(tmp_path, monkeypatch):
    f = tmp_path / "instance_name"
    monkeypatch.setattr("saturn.mdns.conflict._NAME_FILE", f)
    update_instance_name("MySaturn (3)")
    assert f.read_text() == "MySaturn (3)"


# --- UserspaceBackend conflict retry ---

def test_userspace_retries_on_conflict():
    from zeroconf import NonUniqueNameException
    from saturn.mdns.backend import AdvertiseSpec
    from saturn.mdns.userspace import UserspaceBackend

    spec = AdvertiseSpec(name="Saturn", port=8080, txt={"id": "abc"})

    with patch("saturn.mdns.userspace.Zeroconf") as MockZC, \
         patch("saturn.mdns.userspace.get_instance_name", return_value="Saturn"), \
         patch("saturn.mdns.userspace.update_instance_name") as mock_update, \
         patch("saturn.discovery.get_lan_ip", return_value="127.0.0.1"):

        zc = MockZC.return_value
        # First call raises conflict, second succeeds
        zc.register_service.side_effect = [NonUniqueNameException(), None]

        backend = UserspaceBackend()
        backend.advertise(spec)

        assert zc.register_service.call_count == 2
        mock_update.assert_called_once_with("Saturn (2)")


def test_userspace_name_unchanged_on_first_try():
    from saturn.mdns.backend import AdvertiseSpec
    from saturn.mdns.userspace import UserspaceBackend

    spec = AdvertiseSpec(name="Saturn", port=8080, txt={"id": "abc"})

    with patch("saturn.mdns.userspace.Zeroconf") as MockZC, \
         patch("saturn.mdns.userspace.get_instance_name", return_value="Saturn"), \
         patch("saturn.mdns.userspace.update_instance_name") as mock_update, \
         patch("saturn.discovery.get_lan_ip", return_value="127.0.0.1"):

        zc = MockZC.return_value
        zc.register_service.return_value = None

        backend = UserspaceBackend()
        backend.advertise(spec)

        assert zc.register_service.call_count == 1
        mock_update.assert_not_called()


def test_node_id_unchanged_after_rename():
    node_id = "550e8400-e29b-41d4-a716-446655440000"
    from zeroconf import NonUniqueNameException
    from saturn.mdns.backend import AdvertiseSpec
    from saturn.mdns.userspace import UserspaceBackend

    spec = AdvertiseSpec(name="Saturn", port=8080, txt={"id": node_id})

    with patch("saturn.mdns.userspace.Zeroconf") as MockZC, \
         patch("saturn.mdns.userspace.get_instance_name", return_value="Saturn"), \
         patch("saturn.mdns.userspace.update_instance_name"), \
         patch("saturn.discovery.get_lan_ip", return_value="127.0.0.1"):

        zc = MockZC.return_value
        zc.register_service.side_effect = [NonUniqueNameException(), None]

        backend = UserspaceBackend()
        backend.advertise(spec)

        # The txt dict (containing node_id) must be unchanged in the registered service
        registered_info = zc.register_service.call_args_list[1][0][0]
        assert registered_info.properties.get(b"id") == node_id.encode() or \
               registered_info.properties.get("id") == node_id
