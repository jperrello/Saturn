import json
import socket

from saturn.runner import find_available_port, write_service_info, read_service_info, remove_service_info


def test_find_available_port():
    port = find_available_port("127.0.0.1", 49152)
    assert 49152 <= port < 65535
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", port))


def test_find_port_skips_occupied():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        occupied = s.getsockname()[1]
        found = find_available_port("127.0.0.1", occupied)
        assert found != occupied


def test_service_info_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr("saturn.runner.RUN_DIR", tmp_path)

    path = write_service_info("test-svc", 8080, "test-svc-8080")
    assert path.exists()

    info = read_service_info("test-svc")
    assert info is not None
    assert info["port"] == 8080
    assert info["mdns_name"] == "test-svc-8080"
    assert "pid" in info

    remove_service_info("test-svc")
    assert read_service_info("test-svc") is None


def test_read_nonexistent(tmp_path, monkeypatch):
    monkeypatch.setattr("saturn.runner.RUN_DIR", tmp_path)
    assert read_service_info("nonexistent") is None


def test_service_runner_health(monkeypatch):
    from fastapi.testclient import TestClient
    from saturn.config import ServiceConfig, UpstreamConfig
    from saturn.runner import ServiceRunner

    monkeypatch.setenv("SATURN_RUNNER_TOKEN", "tok")
    cfg = ServiceConfig(
        name="test-runner",
        deployment="network",
        upstream=UpstreamConfig(base_url="http://localhost:99999"),
    )
    runner = ServiceRunner(cfg)
    app = runner.create_app()

    with TestClient(app) as client:
        r = client.get("/v1/health", headers={"Authorization": "Bearer tok"})
        assert r.status_code == 200
        data = r.json()
        assert data["saturn"] is True
        assert data["service"] == "test-runner"


def test_service_runner_models_empty(monkeypatch):
    from fastapi.testclient import TestClient
    from saturn.config import ServiceConfig, UpstreamConfig
    from saturn.runner import ServiceRunner

    monkeypatch.setenv("SATURN_RUNNER_TOKEN", "tok")
    cfg = ServiceConfig(
        name="test-runner",
        deployment="network",
        upstream=UpstreamConfig(base_url="http://localhost:99999"),
    )
    runner = ServiceRunner(cfg)
    app = runner.create_app()

    with TestClient(app) as client:
        r = client.get("/v1/models", headers={"Authorization": "Bearer tok"})
        assert r.status_code == 503


def test_write_creates_run_dir(tmp_path, monkeypatch):
    run_dir = tmp_path / "nested" / "run"
    monkeypatch.setattr("saturn.runner.RUN_DIR", run_dir)
    write_service_info("nested-test", 9090, "nested-test-9090")
    assert run_dir.exists()
    assert (run_dir / "nested-test.json").exists()
