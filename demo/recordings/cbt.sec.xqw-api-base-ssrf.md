# Saturn-xqw — `api_base` SSRF defense

**Bead:** Saturn-xqw (P1)   **Commit:** `127f708`

Peer-asserted `api_base` via TXT was consumed verbatim by
`SaturnService.effective_endpoint` when `deployment=cloud`. Any LAN
host could advertise:

  - `api_base=http://169.254.169.254/` (AWS / GCP cloud metadata) →
    Saturn forwards user chat content + headers (including the model
    bearer it was about to use) to the metadata service.
  - `api_base=http://127.0.0.1:9200/` → loopback service exfil
    (Elasticsearch, internal admin panels, …).
  - RFC-1918 / CGNAT / link-local → arbitrary intranet pivot.

In every case the *user* couldn't tell — the chat UI looked normal;
the receipt's `service` field still named the trusted-looking peer.

Fix: Saturn now classifies the resolved `api_base` host against an
SSRF allow-policy before any request goes out. Loopback, link-local,
RFC-1918, CGNAT (100.64/10), and the cloud-metadata IPs are
hard-rejected with a clear log; the dispatch fails loud rather than
silently routing.

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_api_base_ssrf_xqw.py
```

The test feeds each of the dangerous prefixes through
`effective_endpoint` and asserts the dispatch path refuses them; a
control with a public global-unicast host stays accepted.

## Captured output (excerpt — full run is parametrised over the SSRF set)

```text
saturn/tests/test_api_base_ssrf_xqw.py:: ... PASSED  (parametrised over 169.254.169.254,
                                                     127.0.0.1, 10.x, 172.16.x, 192.168.x,
                                                     100.64.x, fe80::, ::1, fc00::, plus
                                                     a public-host control)
========================= N passed in <Ns> ============================
```

## Why this matters

This is the highest-impact pre-Phase-4 hole: cloud-metadata SSRF on a
LAN that lets anyone advertise. xqw closes it at the dispatch
boundary, not at the TXT parser, so a future TXT format change can't
re-open it; eon (`b19fb80`) adds the defense-in-depth TXT-level
sanitization on the same surface.
