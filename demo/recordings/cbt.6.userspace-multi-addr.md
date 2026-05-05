# cbt.6.userspace — `UserspaceBackend.advertise` binds all `routable_addrs`

**Bead:** Saturn-pcj   **Commit:** `78b0a64`

Single-IP `get_lan_ip()` shortcut inside
`UserspaceBackend.advertise()` replaced with
`saturn.mdns.interfaces.routable_addrs()` (cbt.6, `f99354d`). When no
non-loopback addresses are returned (rare — host fully off the
network), we fall back to `[get_lan_ip()]` so the call never silently
turns into a no-op.

Net effect: a multi-NIC host (Wi-Fi + Ethernet, dock with two NICs)
now publishes one A record per routable address instead of leaking a
single arbitrary one. Clients on the *other* interface see the
service.

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_userspace_multi_addr_cbt6_userspace.py
```

## Captured output

```text
saturn/tests/test_userspace_multi_addr_cbt6_userspace.py::
test_userspace_advertise_uses_routable_addrs_for_multi_addr PASSED         [100%]
========================= 1 passed in <Ns> ============================
```
