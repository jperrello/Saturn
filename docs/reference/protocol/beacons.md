# Beacons

A **beacon** is a Saturn responder that publishes credentials for a cloud upstream and never proxies inference traffic. Clients read the credential from TXT and call the upstream directly.

There are two responder shapes:

- **Local responder** — `deployment=local` (or `network`). Advertises an inference server reachable on the LAN (e.g. an Ollama process). No credential needed; the SRV `host:port` is the endpoint.
- **Cloud beacon** — `deployment=cloud`. Mints an ephemeral sub-key against an upstream provider (OpenRouter, DeepInfra), publishes it in `ephemeral_key`, and rotates it. The beacon does **not** see prompt or completion bytes.

## Cloud beacon lifecycle

```
1. Mint        beacon → upstream key API → ephemeral sub-key (short-lived)
2. Publish     beacon updates TXT: ephemeral_key=<jwt>
3. Use         client reads TXT, sends Authorization: Bearer <jwt> to api_base
4. Rotate      before expiry, mint a new sub-key, publish, retain old briefly
5. Revoke      old sub-key explicitly revoked via upstream key API
```

Steps 1 and 5 require an upstream that supports per-key minting and revocation. Saturn currently ships providers for OpenRouter (full mint+revoke) and DeepInfra (mint only — see audit reference below).

## Reference Python beacon defaults

The reference implementation (`saturn/runner.py`) ships these *defaults*, not protocol invariants (Saturn.md:614–615):

| Field | Default | Where set |
|---|---|---|
| Key lifetime | 600 s (10 min) | `expiration_interval` |
| Rotation interval | 300 s (5 min) | `rotation_interval` |
| Overlap window | 300 s (both keys validate) | derived |

A different implementation MAY pick different values. Browsers SHOULD re-read TXT at `rotation_interval / 2` to avoid using a stale key.

## Why ephemeral keys

[Meli et al. (NDSS 2019)](https://www.ndss-symposium.org/wp-content/uploads/2019/02/ndss2019_04B-3_Meli_paper.pdf) found 81% of secrets leaked to GitHub are never revoked. Static-key mitigations (revocation, scanning) act after the damage is done. A 10-minute sub-key inverts the problem: a key extracted from a packet capture or a leaked log expires before any scanner reaches it. The threat model shifts from internet-scale and unbounded to LAN-scoped and bounded by the rotation cycle. Saturn.md:609–625, 1334–1344.

## What goes wrong if the beacon dies

When the beacon loses internet connectivity or crashes, no new keys are minted. Existing keys expire on their normal cadence. Clients fall through to the next priority-ordered instance per the [discovery flow](discovery.md). There is no client-side caching of expired keys.

## Security posture (READ THIS BEFORE DEPLOYING)

> Saturn's beacon mode is designed for trusted local networks — the network you'd plug a printer into. Saturn mints a short-lived sub-key against a parent API key you provide, broadcasts that sub-key over mDNS, and clients use it directly. Two implications:
>
> 1. The sub-key's **per-key spending cap is the actual security boundary.** You must set `beacon.max_budget_usd` (default disabled). If your threat model includes any device on the LAN, set this low.
> 2. Anyone on the local link can sniff the sub-key. Treat the LAN as the audience. Do not run beacon mode on networks where you don't trust every connected device.
>
> If those constraints don't fit your setting, use **proxy mode** instead: Saturn keeps the parent key server-side and proxies chat traffic through its own authenticated `/v1/*` endpoints.

— `SECURITY_AUDIT.md §7.6`

Audit references and known gaps (current branch):

- `saturn/providers/openrouter.py:12-17` — sub-key mint payload missing per-key `limit`. Set the budget cap on the parent key until §7 fixes land.
- `saturn/providers/deepinfra.py:4-11` — `revoke()` is a no-op. DeepInfra sub-keys remain valid until natural expiry.
- `saturn/runner.py:91-102, 142-156, 258-273` — mint, publish, rotate.
- `saturn/config.py:34-38` — defaults that violate the §7.5(4) invariant; review before shipping a beacon to a multi-tenant LAN.

→ [Security model](security.md) · [TXT keys](txt-keys.md) · [Discovery flow](discovery.md)
