"""Saturn-bfx / cbt.8.integrate — advertiser TXT validate + mtrunc wiring.

Per PRE_SPECS_B3.md §17.G.4.3. `SaturnAdvertiser.register()` (currently at
`saturn/discovery.py:513-532`) MUST call `saturn.mdns.txt.validate(...)` on
its TXT properties BEFORE delegating to `backend.advertise()`. On
`TxtTooLarge`:

  1. Prune `models` further (already partially supported via the existing
     200-byte loop), then `capabilities`, then `features`, until under
     `TXT_SAFE_CEILING`.
  2. Set `mtrunc=1` so consumers know the payload is partial.
  3. If still over ceiling after pruning, **raise** `TxtTooLarge` (do NOT
     swallow into a `return False`) — better to refuse to advertise than to
     ship a record that gets fragmented or silently dropped.

Falsifiable oracle:

- **Prune-and-mark:** an advertiser with bloated `capabilities` that pushes
  `_properties()` past the ceiling MUST still produce a props dict that
  passes `validate()` AND carries `mtrunc='1'`.
- **Fail-loud:** an advertiser with bloat in an unprunable field (e.g., a
  pathologically long `api_base`) MUST cause `register()` to raise
  `TxtTooLarge`, not return `False` silently.

NO MOCKS. Real advertiser construction; the registration `backend.advertise`
call is patched out via a benign `_backend` stub since this contract is
about the validate-and-prune surface, not the mDNS transport.
"""

import pytest


def _bloated_advertiser(api_base="http://example.com/v1", caps_count=200, models_count=0):
    from saturn.discovery import SaturnAdvertiser
    adv = SaturnAdvertiser(
        name="bfx-test",
        port=9999,
        deployment="network",
        api_type="openai",
        api_base=api_base,
        priority=10,
        models=[f"model-{i:04d}" for i in range(models_count)],
        capabilities=[f"cap-{i:04d}" for i in range(caps_count)],
        context=8192,
        cost="free",
    )
    return adv


class _StubBackend:
    def __init__(self):
        self.advertised = None
    def advertise(self, spec):
        self.advertised = spec


def test_prune_and_mtrunc_under_capabilities_bloat():
    from saturn.mdns.txt import validate, TXT_SAFE_CEILING
    adv = _bloated_advertiser(caps_count=300)
    props = adv._properties()
    # Validator must accept the pruned props
    n = validate(props)
    assert n <= TXT_SAFE_CEILING, (
        f"_properties() must self-prune capabilities/features so the validator passes; "
        f"got total bytes {n}, ceiling {TXT_SAFE_CEILING}, capabilities len="
        f"{len(props.get('capabilities','').split(','))}"
    )
    assert props.get("mtrunc") == "1", (
        f"after pruning, mtrunc='1' must be set so consumers know the TXT is partial; "
        f"got mtrunc={props.get('mtrunc')!r}"
    )


def test_register_raises_txt_too_large_on_unprunable_bloat():
    from saturn.mdns.txt import TxtTooLarge
    huge_api_base = "http://example.com/" + ("x" * 2000) + "/v1"
    adv = _bloated_advertiser(api_base=huge_api_base, caps_count=10)
    adv._backend = _StubBackend()
    with pytest.raises(TxtTooLarge):
        adv.register()
