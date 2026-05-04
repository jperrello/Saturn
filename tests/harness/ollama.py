import subprocess
import urllib.request

DEFAULT = "qwen2.5:0.5b"


def up(host="http://localhost:11434"):
    try:
        urllib.request.urlopen(f"{host}/api/tags", timeout=2).read()
        return True
    except Exception:
        return False


def has(model):
    out = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=True)
    for line in out.stdout.splitlines()[1:]:
        if line.split() and line.split()[0] == model: return True
    return False


def pull(model):
    subprocess.run(["ollama", "pull", model], check=True)


def ensure(model=DEFAULT):
    if not up(): raise RuntimeError("ollama daemon not running ('ollama serve')")
    if not has(model): pull(model)
    return model
