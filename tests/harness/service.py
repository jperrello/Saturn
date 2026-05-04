import json
import os
import pathlib
import signal
import subprocess
import time

try:
    import tomllib
except ImportError:
    import tomli as tomllib
import tomli_w

ROOT = pathlib.Path.home() / ".saturn"
CONFIG = ROOT / "services"
RUN = ROOT / "run"


def install(name, **fields):
    CONFIG.mkdir(parents=True, exist_ok=True)
    base = {
        "name": name,
        "deployment": "local",
        "api_type": "ollama",
        "priority": 50,
        "upstream": {"base_url": "http://localhost:11434/v1"},
        "server": {"port": 0, "module": "saturn.servers.ollama"},
        "beacon": {"enabled": False},
    }
    for k, v in fields.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k].update(v)
            continue
        base[k] = v
    path = CONFIG / f"{name}.toml"
    with open(path, "wb") as f:
        tomli_w.dump(base, f)
    return path


def edit(name, **fields):
    path = CONFIG / f"{name}.toml"
    if not path.exists(): raise FileNotFoundError(path)
    with open(path, "rb") as f:
        data = tomllib.load(f)
    for k, v in fields.items():
        if isinstance(v, dict) and isinstance(data.get(k), dict):
            data[k].update(v)
            continue
        data[k] = v
    with open(path, "wb") as f:
        tomli_w.dump(data, f)
    return path


def delete(name):
    subprocess.run(["saturn", "config", "delete", name, "--force"],
                   capture_output=True, check=False)
    path = CONFIG / f"{name}.toml"
    if path.exists(): path.unlink()


def start(name, timeout=15.0):
    stop(name)
    log = open(f"/tmp/saturn-{name}.log", "wb")
    proc = subprocess.Popen(["saturn", "run", name], stdout=log, stderr=log,
                            preexec_fn=os.setsid)
    pidfile = RUN / f"{name}.json"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pidfile.exists():
            with open(pidfile) as f:
                meta = json.load(f)
            return {"pid": proc.pid, "port": meta.get("port"), "pidfile": str(pidfile)}
        time.sleep(0.2)
    raise TimeoutError(f"{name} did not register within {timeout}s")


def stop(name):
    subprocess.run(["saturn", "stop", name], capture_output=True, check=False)


def discover(timeout=None):
    out = subprocess.run(["saturn", "discover"],
                         capture_output=True, text=True, check=False)
    services = []
    cur = None
    for line in out.stdout.splitlines():
        s = line.strip()
        if "._saturn._tcp" in s:
            if cur: services.append(cur)
            head = s.split("─", 1)[-1].strip()
            cur = {"name": head.split(".")[0], "raw": s, "txt": {}}
            continue
        if cur and ":" in s:
            kv = s.lstrip("├└─│ ").strip()
            if ":" in kv:
                k, _, v = kv.partition(":")
                cur["txt"][k.strip()] = v.strip()
    if cur: services.append(cur)
    return services


def endpoint():
    out = subprocess.run(["saturn", "endpoint"], capture_output=True, text=True,
                         check=True)
    return out.stdout.strip()
