"""Saturn-cbt.3.c — known_nodes.json cross-process safety.

Per DISCOVERY_AUDIT.md (c). `saturn/mdns/known_nodes.py` uses an in-process
`threading.Lock()` (line 17) and atomic tmp+rename in `save()` (line 52-57).
This is safe within ONE process but unsafe ACROSS processes: two Saturn
instances on the same host racing on `pin()` can lose entries because
load→modify→save is not atomic across processes.

Falsifiable oracle: spawn 2 subprocess clients that each call `pin()` 100
times with distinct (name, node_id) pairs. After both exit, the final
`known_nodes.json` MUST contain all 200 pinned entries.

Currently the test loses some entries to the load-modify-save race (typically
~5-30 per run on macOS, varies by scheduler). The fix is to wrap load+save
under `fcntl.flock(LOCK_EX)`.

NO MOCKS. Real subprocesses, real filesystem, $HOME redirected to tmp_path so
the user's actual `~/.saturn/known_nodes.json` is untouched.
"""

import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest


pytestmark = pytest.mark.timeout(60)


CHILD_SRC = textwrap.dedent('''
    import os, sys
    from saturn.mdns import known_nodes as kn

    prefix = sys.argv[1]
    n = int(sys.argv[2])
    for i in range(n):
        kn.pin(name=f"{prefix}-{i:03d}", node_id=f"node-{prefix}-{i:03d}", host="127.0.0.1")
''')


def _ensure_repo_on_path():
    repo = Path(__file__).resolve().parents[2]
    return str(repo)


def test_concurrent_subprocess_pin_does_not_lose_entries(tmp_path):
    home = tmp_path / "home"
    (home / ".saturn").mkdir(parents=True)
    src = tmp_path / "child.py"
    src.write_text(CHILD_SRC)

    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(home),
        "PYTHONPATH": _ensure_repo_on_path(),
    }

    n = 100
    procs = []
    for prefix in ("a", "b"):
        p = subprocess.Popen(
            [sys.executable, str(src), prefix, str(n)],
            env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        procs.append((prefix, p))

    failures = []
    for prefix, p in procs:
        out, err = p.communicate(timeout=45)
        if p.returncode != 0:
            failures.append((prefix, p.returncode, err.decode(errors="replace")[:600]))

    state_path = home / ".saturn" / "known_nodes.json"
    expected = {f"{p}-{i:03d}" for p in ("a", "b") for i in range(n)}
    nodes = {}
    if state_path.exists():
        try:
            nodes = (json.loads(state_path.read_text()).get("nodes") or {})
        except ValueError as e:
            failures.append(("parse", 0, f"final known_nodes.json is corrupt: {e}"))
    missing = expected - set(nodes.keys())

    assert not failures and not missing, (
        f"cross-process pin race detected. "
        f"subprocess failures={failures!r}; "
        f"missing entries: {len(missing)} of {len(expected)} (e.g. {sorted(missing)[:10]!r}). "
        f"Both symptoms (child crash on os.replace and lost entries) point at the same root: "
        f"saturn/mdns/known_nodes.py serializes load→save only with threading.Lock, not "
        f"fcntl.flock. Wrap save() (or load+save together) in fcntl.flock(LOCK_EX) so "
        f"concurrent writers across processes do not collide on the .tmp file."
    )
