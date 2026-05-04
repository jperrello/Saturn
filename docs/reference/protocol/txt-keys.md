# TXT Record Keys

Normative reference for every key Saturn defines in its TXT record. Each entry is independently anchored — link from prose with `txt-keys.md#<key>`.

## Summary

| Key | Type | Required | Since | Default |
|---|---|---|---|---|
| [`version`](#version) | integer | **MUST** | v0.1 | — |
| [`api_type`](#api_type) | enum | **MUST** | v0.1 | — |
| [`deployment`](#deployment) | enum | **MUST** | v0.1 | — |
| [`priority`](#priority) | integer | **MUST** | v0.1 | — |
| [`api_base`](#api_base) | URL | **MUST** when `deployment=cloud` | v0.1 | — |
| [`ephemeral_key`](#ephemeral_key) | JWT | **MUST** when `deployment=cloud` | v0.1 | — |
| [`rotation_interval`](#rotation_interval) | integer (seconds) | SHOULD when `ephemeral_key` set | v0.1 | `300` |
| [`features`](#features) | comma-list | MAY | v0.1 | — |

Every TXT string MUST be ≤ 255 bytes ([RFC 6763 §6.1](https://datatracker.ietf.org/doc/html/rfc6763#section-6.1)). Browsers MUST ignore unknown keys (forward compatibility).

> **Status: draft — pending spec sign-off.** RFC 3119 stability levels (MUST / SHOULD / MAY) above are the writer's first formalization. The thesis (Saturn.md:568–603) and the v2 redesign draft ([`spec/v0.2/wire-format.md`](../../spec/v0.2/wire-format.md):504–526) both use informal "Required / Conditional / No". Treat the column as a proposal until the spec adopts it.

---

## `version`

```
version=1
```

Saturn protocol version. A browser that does not understand this version MUST NOT route to the instance.

**When to use.** Always. Bump when the schema changes incompatibly.
**Example.** `version=1`
**See also.** [`spec/v0.2/wire-format.md`](../../spec/v0.2/wire-format.md)

---

## `api_type`

```
api_type=openai | ollama | <vendor>
```

Identifies the HTTP API the responder serves. Browsers use this to pick the right client SDK.

**When to use.** Always. `openai` is the default for OpenAI-compatible endpoints (`/v1/chat/completions`, `/v1/models`).
**Example.** `api_type=openai`
**See also.** [HTTP API reference](http-api.md)

---

## `deployment`

```
deployment=local | cloud | network
```

Where the inference happens.

- `local` — same machine or LAN; no credential needed.
- `cloud` — proxies to an off-LAN provider; `api_base` and `ephemeral_key` are required.
- `network` — runs on a dedicated network appliance (e.g. router-edge build).

**When to use.** Always. Determines which other keys become required.
**Example.** `deployment=cloud`
**See also.** [`api_base`](#api_base), [`ephemeral_key`](#ephemeral_key)

---

## `priority`

```
priority=10
```

Routing preference. Lower values are preferred. Browsers MUST sort discovered instances by `priority` ascending and pick the lowest healthy match.

**When to use.** Always. Distinct from the SRV priority field (which Saturn does not use).
**Example.** `priority=10`
**See also.** [Discovery flow](discovery.md)

---

## `api_base`

```
api_base=https://openrouter.ai/api/v1
```

Full base URL for cloud responders. Browsers MUST use this URL instead of constructing one from SRV `host:port`.

**When to use.** Required if `deployment=cloud`. Forbidden otherwise.
**Example.** `api_base=https://api.deepinfra.com/v1/openai`
**See also.** [`ephemeral_key`](#ephemeral_key)

---

## `ephemeral_key`

```
ephemeral_key=eyJhbGciOiJIUzI1NiIs...
```

Short-lived JWT credential minted by a [beacon](beacons.md). Browsers MUST send this as `Authorization: Bearer <ephemeral_key>` to `api_base`.

**When to use.** Required if `deployment=cloud`. Beacons SHOULD set expiration ≤ 600 seconds.
**Example.** `ephemeral_key=eyJ...` (10-minute JWT)
**See also.** [`rotation_interval`](#rotation_interval), [Beacons](beacons.md), [Security model](security.md)

---

## `rotation_interval`

```
rotation_interval=300
```

Seconds between key rotations. The reference Python beacon rotates every 300 s with a 60 s overlap window where both old and new keys validate. Browsers SHOULD re-read TXT at half this interval to avoid stale credentials.

**When to use.** Whenever `ephemeral_key` is set.
**Example.** `rotation_interval=300`
**See also.** [Beacons](beacons.md)

---

## `features`

```
features=chat,tools,vision
```

Comma-separated capability flags. Browsers MAY filter by these (e.g. only route a vision request to instances advertising `vision`).

**When to use.** When the responder supports more than baseline chat. Reserved tokens: `chat`, `tools`, `vision`, `embeddings`, `streaming`. Custom tokens permitted; browsers MUST ignore unknown tokens.
**Example.** `features=chat,tools`
**See also.** [HTTP API](http-api.md)

---

## Reserved key prefixes

- `x-*` — vendor-private. Browsers MUST ignore.
- `_*` — reserved for future Saturn use. Implementations MUST NOT publish.

→ [Wire format](wire-format.md) · [Discovery flow](discovery.md) · [Security model](security.md)
