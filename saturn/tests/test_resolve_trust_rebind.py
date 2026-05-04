"""Saturn-qj5.16.13.1 — wire TrustRebindError into saturn/web.py:_resolve.

Per SECURITY_AUDIT.md §15.3. The TrustRebindError class shipped in saturn/discovery.py
(qj5.16.13 / 150468c) but is never raised. Today a hijack attempt produces a generic
404 'Service not found' — indistinguishable from a stopped service. Frontend banner
(qj5.16.13 commit 3) needs the structured 403.

Falsifier:
  - service NOT in _discovered AND no live config AND a recent rejection in
    known_nodes.load()['rejected'] for that name → _resolve raises HTTPException(403)
    with detail={'error': 'trust_rebind_rejected', 'service', 'expected_prefix',
                  'seen_prefix', 'seen_host', 'remediation'}.
  - service unknown with no rejection on record → existing 404 behaviour preserved.

No mocks of saturn internals — uses monkeypatch on the known_nodes file path so the
test can inject a rejection record without touching the real ~/.saturn/known_nodes.json.
"""

import json

import pytest
from fastapi import HTTPException


def _seed_rejection(tmp_path, monkeypatch, *, name="hijack-svc",
                    expected="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    seen="11111111-2222-3333-4444-555555555555",
                    host="192.168.1.99"):
    """Point known_nodes at tmp_path and write a rejection record for `name`."""
    import saturn.mdns.known_nodes as kn
    fake = tmp_path / "known_nodes.json"
    monkeypatch.setattr(kn, "PATH", fake)
    fake.write_text(json.dumps({
        "version": 1,
        "nodes": {},
        "rejected": [
            {
                "service_name": name,
                "node_id": seen,
                "expected_node_id": expected,
                "host_seen": host,
                "rejected_at": "2026-05-04T12:00:00Z",
                "reason": "rebind_attempt",
            }
        ],
    }))
    return name, expected, seen, host


def test_resolve_raises_403_when_rejection_recorded(tmp_path, monkeypatch):
    name, expected, seen, host = _seed_rejection(tmp_path, monkeypatch)

    import saturn.web as web
    monkeypatch.setattr(web, "_discovered", {}, raising=False)
    monkeypatch.setattr(web, "load_service_config", lambda n: None)
    monkeypatch.setattr(web, "read_service_info", lambda n: None)

    with pytest.raises(HTTPException) as exc:
        web._resolve(name)

    assert exc.value.status_code == 403, (
        f"expected 403 (trust_rebind_rejected); got {exc.value.status_code}. "
        f"Service was rejected per known_nodes; resolver must surface this distinct from a 404."
    )
    detail = exc.value.detail
    assert isinstance(detail, dict), f"detail must be a structured dict; got {type(detail).__name__}"
    assert detail.get("error") == "trust_rebind_rejected"
    assert detail.get("service") == name
    assert detail.get("expected_prefix") == expected[:8], (
        f"expected_prefix must be the first 8 chars of expected_node_id; got {detail.get('expected_prefix')!r}"
    )
    assert detail.get("seen_prefix") == seen[:8]
    assert detail.get("seen_host") == host
    remediation = (detail.get("remediation") or "").lower()
    assert "configure" in remediation and ("trust" in remediation or "node_id" in remediation), (
        f"remediation must point the user at Configure → Service identity → Trust this node_id; got {detail.get('remediation')!r}"
    )


def test_resolve_404_when_unknown_with_no_rejection(tmp_path, monkeypatch):
    """Existing 404 behaviour preserved when there's no rejection on record."""
    import saturn.mdns.known_nodes as kn
    fake = tmp_path / "known_nodes.json"
    monkeypatch.setattr(kn, "PATH", fake)
    fake.write_text(json.dumps({"version": 1, "nodes": {}, "rejected": []}))

    import saturn.web as web
    monkeypatch.setattr(web, "_discovered", {}, raising=False)
    monkeypatch.setattr(web, "load_service_config", lambda n: None)
    monkeypatch.setattr(web, "read_service_info", lambda n: None)

    with pytest.raises(HTTPException) as exc:
        web._resolve("never-heard-of-it")
    assert exc.value.status_code == 404, (
        f"unknown service with no rejection must remain a 404; got {exc.value.status_code}"
    )


def test_resolve_403_takes_precedence_over_404(tmp_path, monkeypatch):
    """When BOTH 'unknown' AND 'rejection recorded' are true, the resolver MUST 403, not 404.
    A 404 in this case is the original bug — frontend cannot distinguish a hijack attempt from
    a stopped service."""
    name, *_ = _seed_rejection(tmp_path, monkeypatch, name="ambiguous-svc")

    import saturn.web as web
    monkeypatch.setattr(web, "_discovered", {}, raising=False)
    monkeypatch.setattr(web, "load_service_config", lambda n: None)
    monkeypatch.setattr(web, "read_service_info", lambda n: None)

    with pytest.raises(HTTPException) as exc:
        web._resolve(name)
    assert exc.value.status_code == 403, (
        f"with rejection on record, _resolve must 403 even though service is also "
        f"unknown to _discovered/config — the rejection signal is more specific. got {exc.value.status_code}"
    )
