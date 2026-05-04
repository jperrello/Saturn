# Saturn Protocol Spec

Two version axes coexist. Don't conflate them:

- **TXT `version`** — single integer carried in every advertisement. The thesis-time schema is `version=1`; that is the canonical wire format Saturn implementations interoperate against today (Saturn.md:573–575).
- **Spec document version** (`v0.1` / `v0.2` directories here) — the documentation's own version axis, used to file *proposed* redesigns separately from canonical material. The DOCS_PATTERNS-recommended `v0.x` scheme is orthogonal to the single-integer TXT field.

| Spec doc | Status | Maps to TXT | Documents |
|---|---|---|---|
| **v0.2** | **Proposed redesign** (not yet canonical) | proposes new `v=2` schema | [Proposal](v0.2/proposal.md) · [Wire format](v0.2/wire-format.md) |
| v0.1 | Canonical (current implementations) | `version=1` | folded into [reference/protocol/wire-format.md](../reference/protocol/wire-format.md) |

Stability markers used in spec documents:

- **Stable** — implementations MAY rely on the field across spec versions.
- **Draft** — subject to change before promotion to Stable.
- **Deprecated** — scheduled for removal in a future spec version.

→ [Implementations conformance](../implementations/index.md#adding-a-new-implementation)
