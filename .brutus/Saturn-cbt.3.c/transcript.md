# Saturn-cbt.3.c — known_nodes.json cross-process safety

*2026-05-05T05:04:01Z by Showboat 0.6.1*
<!-- showboat-id: 9bae5c84-d55c-4b02-bc11-0314dbc09af4 -->

Red phase. saturn/mdns/known_nodes.py serializes only with threading.Lock — two processes pinning concurrently race on the .tmp file. Test spawns 2 subprocesses each pinning 100 distinct nodes; expects all 200 in the final JSON. Currently surfaces as either subprocess crash on os.replace (FileNotFoundError) or lost entries — both are race symptoms. Real subprocesses, real filesystem, HOME redirected to tmp_path. NO MOCKS.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_known_nodes_cross_proc_cbt3c.py --no-header -rN --tb=line 2>&1 | tail -10
```

```output
    assert (not [('a', 1, 'Traceback (most recent call last):\n  File "/private/var/folders/zs/6ms437qs2nd0sdk8knf1lgwr0000gp/T/pytest...)\nFileNotFoundError: [Errno 2] No such file or directory: \'/private/var/folders/zs/6ms437qs2nd0sdk8knf1lgwr0000gp/')])
/Users/jperr/Documents/Saturn/saturn/tests/test_known_nodes_cross_proc_cbt3c.py:89: AssertionError: cross-process pin race detected. subprocess failures=[('a', 1, 'Traceback (most recent call last):\n  File "/private/var/folders/zs/6ms437qs2nd0sdk8knf1lgwr0000gp/T/pytest-of-jperr/pytest-180/test_concurrent_subprocess_pin0/child.py", line 8, in <module>\n    kn.pin(name=f"{prefix}-{i:03d}", node_id=f"node-{prefix}-{i:03d}", host="127.0.0.1")\n  File "/Users/jperr/Documents/Saturn/saturn/mdns/known_nodes.py", line 85, in pin\n    save(state)\n  File "/Users/jperr/Documents/Saturn/saturn/mdns/known_nodes.py", line 57, in save\n    os.replace(tmp, PATH)\nFileNotFoundError: [Errno 2] No such file or directory: \'/private/var/folders/zs/6ms437qs2nd0sdk8knf1lgwr0000gp/')]; missing entries: 20 of 200 (e.g. ['a-081', 'a-082', 'a-083', 'a-084', 'a-085', 'a-086', 'a-087', 'a-088', 'a-089', 'a-090']). Both symptoms (child crash on os.replace and lost entries) point at the same root: saturn/mdns/known_nodes.py serializes load→save only with threading.Lock, not fcntl.flock. Wrap save() (or load+save together) in fcntl.flock(LOCK_EX) so concurrent writers across processes do not collide on the .tmp file.
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 1 failed, 1 warning in 0.48s =========================
```
