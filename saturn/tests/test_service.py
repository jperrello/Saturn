from saturn.discovery import SaturnService


def test_is_beacon(beacon):
    assert beacon.is_beacon is True


def test_is_not_beacon(service):
    assert service.is_beacon is False


def test_cloud_without_key_not_beacon():
    s = SaturnService(name="x", host="h", port=1, deployment="cloud", ephemeral_key="")
    assert s.is_cloud is True
    assert s.is_beacon is False


def test_is_cloud(beacon):
    assert beacon.is_cloud is True


def test_is_not_cloud(service):
    assert service.is_cloud is False


def test_is_network(service):
    assert service.is_network is True


def test_is_not_network(beacon):
    assert beacon.is_network is False


def test_effective_endpoint_cloud_with_base(beacon):
    assert beacon.effective_endpoint == "https://api.deepinfra.com/v1/openai"


def test_effective_endpoint_cloud_without_base():
    s = SaturnService(name="x", host="1.2.3.4", port=9000, deployment="cloud", api_base="")
    assert s.effective_endpoint == "http://1.2.3.4:9000/v1"


def test_effective_endpoint_network(service):
    assert service.effective_endpoint == "http://192.168.1.50:8080/v1"


def test_endpoint(service):
    assert service.endpoint == "http://192.168.1.50:8080"


def test_mcp_endpoint(service):
    assert service.mcp_endpoint == "http://192.168.1.50:8080/mcp"


def test_has_model(service):
    assert service.has_model("llama3.2") is True
    assert service.has_model("gpt-4") is False


def test_has_capability(service):
    assert service.has_capability("chat") is True
    assert service.has_capability("vision") is False


def test_has_all_capabilities(service):
    assert service.has_all_capabilities(["chat", "code"]) is True
    assert service.has_all_capabilities(["chat", "vision"]) is False


def test_has_all_capabilities_empty(service):
    assert service.has_all_capabilities([]) is True


def test_defaults():
    s = SaturnService(name="minimal", host="localhost", port=8080)
    assert s.version == "1.0"
    assert s.deployment == "network"
    assert s.api_type == "openai"
    assert s.priority == 100
    assert s.models == []
    assert s.capabilities == []
    assert s.context == 4096
    assert s.cost == "unknown"
    assert s.ephemeral_key == ""
    assert s.api_base == ""
