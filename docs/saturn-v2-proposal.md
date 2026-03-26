# Saturn v2 mDNS Proposal

**For:** Joey (Saturn creator)
**Date:** 2026-03-25
**TL;DR:** Saturn's current network discovery has three real bugs that affect everyday use,
and four improvements that would make it faster and more correct. Here's what they are, why
they matter, and what order to tackle them in.

---

## What This Is About

Saturn finds AI services on your local network using a protocol called mDNS — the same thing
your Mac uses to find printers and Apple TVs. Specifically, Saturn uses a Python library called
`python-zeroconf` to do this.

That library works well in most cases, but there are some gaps between what it does and what
the underlying protocol specification (RFC 6762) requires. A research document
(`docs/mdns-os-research.md`) goes deep on what mDNS is supposed to do at the OS level. Comparing
that against Saturn's code revealed several issues.

---

## The Three Real Bugs

### Bug 1: Discovery is silently broken on every Mac (including yours)

**What's happening:** On macOS, Apple's built-in mDNS daemon (`mDNSResponder`) controls the
mDNS network port exclusively. When python-zeroconf tries to use it, the OS blocks access.
python-zeroconf's workaround is to send responses from a random port instead of the required
port 5353.

**Why it matters:** The mDNS protocol spec explicitly says responses MUST come from port 5353.
Any correctly-implemented mDNS client (other Macs, proper Linux setups, iOS) will see Saturn's
announcements come from a random port and either ignore them or deprioritize them.

**What this looks like day-to-day:** Saturn appears to work fine when you test it on your own
machine (because your machine's python-zeroconf is also using the same workaround and
understands it). But if you're testing multi-machine discovery — a Mac trying to find a Saturn
node on a Linux machine, or vice versa — the Mac's Saturn may not show up correctly on the Linux
side.

**The fix:** On macOS, instead of fighting with `mDNSResponder` for the port, hand the job to
it. Apple provides a proper API (`dns_sd.h` / Bonjour) that lets any app register and discover
services by talking to `mDNSResponder` through a local socket. No port conflict, fully RFC
compliant, zero extra dependencies (it's part of macOS). On Linux, the equivalent is Avahi, and
the same pattern applies.

---

### Bug 2: Two Saturn nodes on the same network can silently clobber each other

**What's happening:** Every Saturn service registers a name like `myservice-8080._saturn._tcp.local.`
on the network. mDNS requires that before claiming a name, you "probe" the network to check if
anyone else is using it. If there's a conflict, the protocol says you must choose a different
name (e.g., `myservice-8080 (2)`).

python-zeroconf does the probing correctly. The bug is in Saturn: when a conflict is detected
and the service is renamed, Saturn doesn't notice. It just logs an error and returns `False`
from `register()`. No retry, no renamed version, no notification to the caller. The service
silently disappears from the network.

**Why it matters:** If you run two Saturn nodes with the same service name on the same network
segment, one of them will fail to register and nobody will know. This gets more likely as more
people use Saturn or as services restart in quick succession.

**The fix:** Catch the name conflict, automatically rename (e.g., append ` (2)`, ` (3)`), and
re-register under the new name. Also add a stable UUID to each service's metadata (separate from
the name) so clients can track "which node is which" even if names change. This UUID gets saved
to `~/.saturn/node_id` and persists across restarts.

---

### Bug 3: `discover()` uses a timer instead of a protocol signal

**What's happening:** When Saturn scans for services, it runs a loop that breaks when it hasn't
seen a new service for 1 second (`settle_time`). It also waits 2 extra seconds at startup to
scan for existing services before even registering (`_find_available_priority()`).

**Why it matters:**
- On fast networks, you're waiting 1 second for nothing — all the services announced themselves
  in 200ms
- On slow or congested networks, 1 second might not be enough — you cut off early and miss peers
- The 2-second pre-registration scan happens every single time a service starts, adding 2 seconds
  to startup for zero benefit (priority collision is extremely unlikely and recoverable anyway)

The mDNS protocol itself has a "I'm done" signal. On Linux/Avahi it's called `ALL_FOR_NOW`. On
macOS/Bonjour it's the absence of a `more coming` flag in the response. Both mean "the daemon
has flushed its cache and sent the first round of queries — there's nothing more immediately
coming." Saturn should use these signals instead of a timer.

**The fix:** Use the protocol's built-in settle signal. Discovery then returns as fast as the
network responds (typically 200–500ms) rather than always waiting 1–3 seconds. Remove the 2s
pre-registration scan entirely.

---

## The Four Improvements (Not Bugs, But Worth Doing)

### Improvement 1: Add a stable node identity

Right now, Saturn nodes are identified entirely by their mDNS instance name. If a name changes
(due to a conflict rename, or even just restarting the service on a different port), clients
lose track of which node they were talking to.

The fix is simple: add a `id=<uuid>` field to each node's mDNS advertisement. This UUID is
generated once, saved to `~/.saturn/node_id`, and never changes. Clients key their state on
this UUID instead of the name. Names can change; the UUID doesn't.

This is already recommended by the DNS-SD specification (RFC 6763 §6.3).

---

### Improvement 2: Add role-based browsing with DNS-SD subtypes

Right now, if you want only "coordinator" nodes, you have to browse all Saturn services and
filter by the `role=` TXT field after downloading everyone's metadata.

DNS-SD subtypes let you register additional labels alongside your primary service:
```
_coordinator._sub._saturn._tcp.local.
_worker._sub._saturn._tcp.local.
```

A client that only wants coordinators browses `_coordinator._sub._saturn._tcp.local.` and only
receives coordinator results — no TXT record download needed, no filtering required.

This is a small change (a few extra lines in the registration code) with a nice payoff for
larger Saturn networks.

---

### Improvement 3: Tighten up the TXT record schema

The metadata Saturn broadcasts with each service has grown organically. A few cleanup items:

- Shorten key names (`deployment` → `dep`, `version` → `v=2`) to save space — TXT records have
  a practical 400-byte limit before link reliability degrades
- Add `mtrunc=1` when the models list was truncated so clients know to call `/v1/models` for the
  full list
- Keep backward-compatible keys alongside new ones for a release

---

### Improvement 4: Graceful shutdown on SIGKILL / OOM

When Saturn shuts down cleanly (Ctrl+C, `systemctl stop`), it sends "goodbye" packets that tell
the network "I'm gone" immediately. But if the process is killed hard (`kill -9`, kernel OOM
kill, power failure), no goodbyes are sent. Other nodes on the network continue to believe the
service is available for up to 2 minutes (the A record TTL) before they figure out it's gone.

There's no perfect fix for hard kills (that's fundamental to the protocol — the research doc
describes this as a ~24-30s window in the worst case). But the current code registers cleanup
via `atexit`, which only runs on normal Python exit. It should also explicitly handle `SIGTERM`
(which systemd sends before force-killing), and the credential rotation in the beacon should be
smoothed out to avoid a brief visibility gap.

---

## Security Notes

Two things came up that are worth being aware of:

**Avahi CVEs (2025–2026):** Three denial-of-service vulnerabilities were fixed in Avahi 0.9-rc3
(released January 2026). They can be triggered by malformed mDNS packets from the local network.
No API changes — just make sure production Linux systems are updated. Saturn itself isn't
affected directly (it's a client, not the daemon), but an attacker crashing Avahi would take
down Saturn's discovery.

**Beacon key in mDNS:** The beacon advertiser broadcasts the ephemeral API key as a TXT field
in an mDNS packet. This is intentional (it's how clients discover the key), but it means anyone
on the local network who can receive mDNS can read the key. The key is short-lived by design,
but it would be worth setting the TXT record's TTL to match the key's actual expiry time, so
network caches don't serve expired keys.

---

## Priority Order

Here's how I'd sequence the work:

| # | Change | Why first |
|---|--------|-----------|
| 1 | Add `id=<uuid>` stable identity to TXT records | Zero risk, immediately useful, prerequisite for conflict fix |
| 2 | Fix `discover()` settle detection | Removes fragile sleeps, faster startup, improves test suite |
| 3 | Bonjour backend for macOS | Fixes the RFC violation on the platform you develop on |
| 4 | Avahi backend for Linux | Fixes the privilege/double-announce issues on production |
| 5 | Conflict handling (rename + re-probe) | Depends on stable id= being in place |
| 6 | DNS-SD subtypes | Low effort, nice feature for role browsing |
| 7 | TXT schema tightening | Low risk, good hygiene |
| 8 | Windows DNS-SD API | Only if Windows is a target |

Items 1 and 2 are small, pure-Python changes that can ship quickly and have immediate impact
on test reliability. Items 3 and 4 are the architectural improvements that make Saturn
production-grade on real networks.

The detailed engineering spec for all of this is in `docs/saturn-v2-technical-spec.md`.
