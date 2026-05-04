import json
import os
import pathlib
import urllib.error
import urllib.request

API = "https://openrouter.ai/api/v1/keys"


def _key():
    k = os.environ.get("OPENROUTER_PROVISIONING_KEY")
    if k: return k
    env = pathlib.Path(__file__).resolve().parents[2] / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("OPENROUTER_PROVISIONING_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("OPENROUTER_PROVISIONING_KEY not set and not in .env")


def _req(method, path="", body=None):
    url = API + (f"/{path}" if path else "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {_key()}",
        "content-type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def list():
    return _req("GET").get("data", [])


def create(name, limit=0.10):
    return _req("POST", body={"name": name, "limit": limit})


def update(hash_, **fields):
    return _req("PATCH", path=hash_, body=fields)


def revoke(hash_):
    return _req("DELETE", path=hash_)
