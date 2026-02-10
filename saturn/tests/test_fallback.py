import json


def test_health(fallback_client):
    r = fallback_client.get("/v1/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["saturn"] is True


def test_models(fallback_client):
    r = fallback_client.get("/v1/models")
    assert r.status_code == 200
    data = r.json()
    ids = [m["id"] for m in data["data"]]
    assert "dont_pick_me" in ids


def test_completion_non_streaming(fallback_client):
    r = fallback_client.post("/v1/chat/completions", json={
        "model": "dont_pick_me",
        "messages": [{"role": "user", "content": "hello"}],
    })
    assert r.status_code == 200
    data = r.json()
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert len(data["choices"][0]["message"]["content"]) > 0


def test_completion_streaming(fallback_client):
    r = fallback_client.post("/v1/chat/completions", json={
        "model": "dont_pick_me",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": True,
    })
    assert r.status_code == 200

    lines = [l for l in r.text.strip().split("\n") if l.startswith("data: ")]
    assert len(lines) >= 2

    last = lines[-1]
    assert last == "data: [DONE]"

    first_data = json.loads(lines[0][6:])
    assert first_data["object"] == "chat.completion.chunk"


def test_wrong_model(fallback_client):
    r = fallback_client.post("/v1/chat/completions", json={
        "model": "nonexistent",
        "messages": [{"role": "user", "content": "hello"}],
    })
    assert r.status_code == 400


def test_invalid_body(fallback_client):
    r = fallback_client.post("/v1/chat/completions", json={"bad": "data"})
    assert r.status_code == 422
