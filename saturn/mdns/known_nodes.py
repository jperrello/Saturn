import json
import os
import stat
import threading
import time
from pathlib import Path
from typing import Optional

import logging

logger = logging.getLogger(__name__)

PATH = Path.home() / ".saturn" / "known_nodes.json"
SCHEMA_VERSION = 1
MAX_REJECTED = 50

_lock = threading.Lock()
_warned_mode = False


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _safe_mode() -> bool:
    global _warned_mode
    if not PATH.exists():
        return True
    st = PATH.stat()
    if st.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        if not _warned_mode:
            logger.warning(f"{PATH} mode 0{oct(st.st_mode & 0o777)[2:]} too wide; skipping TOFU until 0600")
            _warned_mode = True
        return False
    return True


def load() -> dict:
    if not PATH.exists():
        return {"version": SCHEMA_VERSION, "nodes": {}, "rejected": []}
    try:
        data = json.loads(PATH.read_text())
    except (OSError, ValueError) as e:
        logger.warning(f"failed to read {PATH}: {e}")
        return {"version": SCHEMA_VERSION, "nodes": {}, "rejected": []}
    data.setdefault("version", SCHEMA_VERSION)
    data.setdefault("nodes", {})
    data.setdefault("rejected", [])
    return data


def save(state: dict) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    os.chmod(tmp, 0o600)
    os.replace(tmp, PATH)


def known_node_id(name: str) -> Optional[str]:
    if not _safe_mode():
        return None
    with _lock:
        entry = load()["nodes"].get(name)
        return entry["node_id"] if entry else None


def pin(name: str, node_id: str, host: str) -> None:
    with _lock:
        state = load()
        existing = state["nodes"].get(name)
        if existing and existing["node_id"] == node_id:
            existing["last_seen"] = _now()
            existing["host_seen"] = host
        else:
            if existing:
                return
            state["nodes"][name] = {
                "node_id": node_id,
                "first_seen": _now(),
                "last_seen": _now(),
                "host_seen": host,
                "trusted": True,
            }
        save(state)


def record_rejection(name: str, node_id: str, host: str, reason: str, expected_node_id: str = "") -> None:
    with _lock:
        state = load()
        for r in state["rejected"]:
            if r["service_name"] == name and r["node_id"] == node_id:
                r["rejected_at"] = _now()
                r["host_seen"] = host
                if expected_node_id:
                    r["expected_node_id"] = expected_node_id
                save(state)
                return
        state["rejected"].append({
            "service_name": name,
            "node_id": node_id,
            "expected_node_id": expected_node_id,
            "host_seen": host,
            "rejected_at": _now(),
            "reason": reason,
        })
        if len(state["rejected"]) > MAX_REJECTED:
            state["rejected"] = state["rejected"][-MAX_REJECTED:]
        save(state)


def latest_rejection(name: str) -> Optional[dict]:
    with _lock:
        state = load()
        matches = [r for r in state["rejected"] if r["service_name"] == name]
        if not matches:
            return None
        return matches[-1]


def attest(name: str, node_id: str, host: str) -> None:
    with _lock:
        state = load()
        state["nodes"][name] = {
            "node_id": node_id,
            "first_seen": _now(),
            "last_seen": _now(),
            "host_seen": host,
            "trusted": True,
        }
        state["rejected"] = [r for r in state["rejected"] if not (r["service_name"] == name and r["node_id"] == node_id)]
        save(state)


def forget(name: str) -> None:
    with _lock:
        state = load()
        state["nodes"].pop(name, None)
        save(state)
