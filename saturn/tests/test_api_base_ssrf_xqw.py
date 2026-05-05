"""Saturn-xqw — api_base TXT SSRF / route hijack (P1).

Per FAILOVER_SECURITY.md §(B). The TXT field `api_base` is consumed
verbatim by `SaturnService.effective_endpoint` (saturn/discovery.py:115-119)
when `deployment="cloud"`. Both `api_base` and `deployment` are
peer-asserted via mDNS — any host on the LAN can advertise:

  api_base=http://169.254.169.254/   (AWS instance metadata)
  api_base=http://127.0.0.1:9200/    (internal Elastic / etc.)
  api_base=http://evil.example/      (off-LAN exfil)
  deployment=cloud

…and Saturn will route user chat content + any forwarded headers to that
URL. Exploitable today on any LAN-trust deployment.

Falsifiable oracle: a hostile api_base on a discovered service MUST NOT
flow through `effective_endpoint`. The hostile value MUST be either:

  (a) rejected at resolve time (`_to_service` returns the SaturnService
      with `api_base=""`), OR
  (b) rejected at consume time (`effective_endpoint` returns the
      benign `http://{host}:{port}/v1` fallback OR raises).

The implementer picks (a) or (b); brutus does not prescribe. Doing
**neither** (today's behavior) is forbidden.

Tested vectors (each must be neutralized):

  - http://169.254.169.254/    (link-local — AWS/Azure/GCP metadata)
  - http://127.0.0.1:9200/     (loopback — internal services)
  - http://10.0.0.5/v1/        (RFC-1918 — internal LAN)
  - http://192.168.1.1/v1/     (RFC-1918)
  - http://172.16.0.1/v1/      (RFC-1918)
  - http://[::1]/              (IPv6 loopback)
  - http://[fe80::1]/          (IPv6 link-local)
  - http://[fc00::1]/          (IPv6 ULA)
  - ftp://example.com/         (non-https scheme — even for cloud)

Plus a positive control: `https://api.openai.com/v1` is preserved.

NO MOCKS. Pure synthesis of `ServiceRecord`/`SaturnService` instances;
no network.
"""

import pytest


pytestmark = pytest.mark.timeout(15)


HOSTILE = [
    "http://169.254.169.254/",
    "http://169.254.169.254/latest/meta-data/",
    "http://127.0.0.1:9200/",
    "http://localhost:9200/",
    "http://10.0.0.5/v1/",
    "http://192.168.1.1/v1/",
    "http://172.16.0.1/v1/",
    "http://100.64.0.1/v1/",          # CGNAT
    "http://[::1]/",
    "http://[fe80::1]/",
    "http://[fc00::1]/",
    "http://[fd12:3456::1]/",
    "ftp://api.openai.com/v1",        # non-https/http scheme — should not pass either
    "javascript:alert(1)",            # nonsense scheme
]


SAFE = "https://api.openai.com/v1"


def _to_service_with_api_base(api_base):
    """Run a synthetic ServiceRecord through SaturnDiscovery._to_service."""
    from saturn.discovery import SaturnDiscovery
    from saturn.mdns.backend import ServiceRecord
    d = SaturnDiscovery(backend=False)
    rec = ServiceRecord(
        name="hostile-peer",
        node_id="abcd1234",
        host="192.168.1.99",
        port=8443,
        txt={
            "version": "1.0",
            "deployment": "cloud",
            "api_type": "openai",
            "api_base": api_base,
            "priority": "10",
            "models": "test-model",
        },
    )
    return d._to_service(rec)


@pytest.mark.parametrize("hostile", HOSTILE)
def test_hostile_api_base_does_not_flow_through_effective_endpoint(hostile):
    s = _to_service_with_api_base(hostile)

    # Acceptable: (a) api_base sanitized to "" at resolve, or
    # (b) effective_endpoint returns the host:port fallback / raises.
    sanitized_at_resolve = (s.api_base == "")
    benign_fallback = False
    raised = False
    try:
        ep = s.effective_endpoint
        # Must NOT equal or contain the hostile value
        if hostile in ep or ep == hostile:
            benign_fallback = False
        else:
            benign_fallback = True
    except Exception:
        raised = True

    guarded = sanitized_at_resolve or benign_fallback or raised
    assert guarded, (
        f"hostile api_base {hostile!r} flowed through unguarded. "
        f"effective_endpoint returned {s.effective_endpoint!r}; api_base field "
        f"on SaturnService is {s.api_base!r}. Per FAILOVER_SECURITY.md §(B) "
        f"P1, sanitize api_base at saturn/discovery.py:175 (resolve-side) AND "
        f"validate at saturn/discovery.py:115-119 (consume-side). Reject "
        f"non-https schemes, RFC-1918, loopback, link-local, CGNAT, IPv6 "
        f"ULA, and IPv6 link-local hosts."
    )


def test_safe_https_api_base_is_preserved():
    s = _to_service_with_api_base(SAFE)
    # The legitimate cloud endpoint MUST flow through unchanged so the
    # validation doesn't break real cloud deployments.
    assert s.effective_endpoint == SAFE, (
        f"validation must NOT reject safe https:// public hosts; "
        f"got effective_endpoint={s.effective_endpoint!r}, expected {SAFE!r}"
    )
