# Split-Brain Patterns — Research Synthesis

**Context:** Saturn currently has TOFU pinning + allowlist (qj5.16.13) but no detection for the case where two services both advertise the same logical identity (or contend for the same priority slot) with different `node_id`s. This is the discovery-layer split-brain. Below: how other systems detect, resolve, and what fits Saturn's zero-config home/office model.

Scope note: Saturn is **not** a consensus system. Peers don't replicate state. The "split brain" risk here is *client confusion* — two equally-priority services answering the same role, clients oscillating or silently picking one. Most consensus literature (Raft/Paxos) is over-engineered for this. The relevant analogues are mDNS conflict resolution, DNS resolver tie-breaking, and client-side leader hints.

---

## (a) Detection mechanisms

| System | Mechanism | Signal |
|---|---|---|
| **etcd / Raft** | Term numbers + heartbeat timeout. A partitioned old leader sees no quorum acks → steps down. New leader has higher term; clients reject lower-term writes. | Quorum + monotonic term. |
| **Consul (Serf gossip)** | Gossip membership detects unreachable peers within seconds. Server-side: lost quorum → readonly. Symptoms in split-brain: "servers repeatedly hold elections," divergent member lists. | Gossip convergence + Raft quorum on the server tier. |
| **ZooKeeper / Zab** | Quorum required for any write. Minority partition becomes unavailable rather than diverging. | Majority count. |
| **Kubernetes leader election** | Lease object in `coordination.k8s.io`; `LeaseDurationSeconds` + `RenewTime`. A would-be leader observes the lease and only acts if expired. **Fencing tokens** (monotonic lease generation) reject stale leaders at the storage tier. | Lease + fencing token. |
| **mDNS / DNS-SD (RFC 6762 §9)** | **Probing.** Before claiming a name, host sends 3 probe queries 250ms apart. If anyone answers with a conflicting record, the prober loses (lexicographic tiebreak on rdata) and renames (`-2`, `-3`, …). Post-claim conflicts also trigger rename. | Multicast probe + lexicographic compare. |
| **DNS resolvers (unicast)** | No standard conflict detection — resolvers happily return whichever upstream answered. Multi-A records → round-robin or random selection. Inconsistency surfaces only via client-side observation (different answers from different resolvers). | None at protocol layer. |

**Key insight for Saturn:** the closest precedents aren't Raft (Saturn has no shared log to protect) — they're **(1) mDNS probing**, which already runs *under* Saturn at the discovery layer, and **(2) Kubernetes lease + fencing**, which is a client-coordinated single-leader pattern without requiring replicated state.

### Detection signals available to Saturn today

1. **Discovery cache cardinality.** During `discover()`, count services advertising the same priority *or* same logical role. Two with `priority=10` and different `node_id`s = split-brain candidate.
2. **mDNS conflict callbacks.** `mdns_sd` (Rust) and Avahi expose conflict-event callbacks per RFC 6762 §9 — Saturn's responder layer can already see "another host claims my service name." Currently unused for split-brain reporting.
3. **TOFU pin mismatch.** When a previously-pinned `node_id` is replaced by a new one at the same address/port, that's either legitimate rekey or a takeover. Already surfaced.
4. **Cross-resolve disagreement.** If two parallel resolves of the same instance name return different TXT/SRV (e.g., different `node_id` in TXT), that's split-brain at the responder layer.

---

## (b) Resolution strategies

| Strategy | Where it's used | Verdict for Saturn |
|---|---|---|
| **Kill one (STONITH / fencing)** | Pacemaker, SIOS LifeKeeper, hardware HA. Requires power-management or storage-fencing path. | ❌ Not appropriate. Saturn has no authority to kill a peer process on someone else's machine. |
| **Quorum / vote** | etcd, Consul servers, ZK. Requires ≥3 odd-count members and persistent membership. | ❌ Saturn peers come and go (laptops, phones). No stable quorum set. |
| **Run both (eventual consistency, AP side of CAP)** | Cassandra, Dynamo. Accept divergence, reconcile later. | ❌ Saturn's chat turns are not commutative — running the same turn against two different services is wasteful and confusing. |
| **Lexicographic tiebreak** | mDNS probing (RFC 6762 §9). Higher rdata wins; loser renames. | ✅ Cheap, deterministic, already in stack. Good for breaking ties on `priority`. |
| **Lease + fencing token** | k8s `coordination.k8s.io/Lease`. Monotonic counter; stale holders rejected at sink. | ⚠️ Partial fit. Saturn has no central sink, but a lightweight TXT-record lease (`epoch=N`) lets clients prefer the higher epoch. |
| **Ask the operator** | Avahi's `-2` rename is automatic; some setups disable it (`AVAHI_PUBLISH_NO_REVERSE`) and surface the conflict. Pacemaker's "split-brain mail." | ✅ Saturn's UX model — surface the ambiguity in the Network Scan tab and let the operator pin one. Aligns with B.3 AP-isolation UX pattern. |
| **Sticky session + first-wins** | Most service meshes during transient flap (also Saturn's failover spec B.2). | ✅ Already partially implemented — extend to "stick to whichever node_id the user last interacted with, even at equal priority." |

---

## (c) What fits Saturn's zero-config home/office model

Saturn's deployment surface:
- 1–10 nodes on a LAN/VPN, mostly laptops + a desktop or two.
- No persistent quorum membership; nodes join/leave constantly.
- No storage to fence; the "shared resource" is the user's chat session, which is owned by the *client*, not the cluster.
- Operators are humans on the LAN, often the same person who owns both services.

Implications:
- **Strong consensus is overkill.** Don't import Raft.
- **Silent auto-resolution is wrong.** mDNS-style auto-rename hides real configuration mistakes (operator accidentally ran two Saturn servers on the same laptop pair). The user wants to *know*.
- **Client-side selection is the right tier.** Saturn already does priority-driven selection — split-brain handling lives there, not in a server-tier coordinator.
- **The operator is the tiebreaker.** A "two services, same priority, different identity" event is almost always either (a) intentional redundancy where the user has a clear preference, or (b) a misconfiguration. Both want operator attention.

---

## (d) Recommended approach (future bead spec)

**Bead title:** `Saturn-cbt.X — split-brain detection + operator surface`
**Type:** feature
**Priority:** P2

### Falsifiable acceptance

Given two Saturn servers on the LAN both advertising `priority=10` with different `node_id`s, a client `discover()` call must:

1. **Detect** the collision and emit `saturn_meta.discovery.split_brain` with both candidates' `{node_id, addr, advertised_priority, first_seen, txt_epoch}`.
2. **Pick deterministically** for the current turn using a documented tiebreak chain:
   1. Higher `epoch` in TXT (if present — see lease note below).
   2. Operator pin (allowlist priority override) if set.
   3. Sticky last-used `node_id` from local state file.
   4. Lexicographic tiebreak on `node_id` (matches RFC 6762 §9 spirit; deterministic across clients without coordination).
3. **Surface** the collision in the Web-UI Network Scan tab as a yellow warning row: "Two services claim priority 10. Currently using `<node_id_short>`. [Pin this one] [Pin the other] [Ignore]."
4. **Receipt integration:** `saturn_meta.routing.split_brain_observed: true` plus the candidate list when a turn was served under a detected collision.

### Optional: TXT epoch lease (lightweight)

Add `epoch=<unix_ts_seconds>` to the Saturn TXT record, set at server start. On collision, prefer higher epoch (newer instance — covers the "old server is stuck, new one is the real one" case without requiring the operator to intervene). This is *not* a Raft-style monotonic counter; it's a hint, and the operator pin always overrides. Cost: 16 bytes in TXT, well under the 1500-byte ceiling B.3 §17.G.4 imposes.

### Test plan (no mocks)

- Spin two Saturn servers via the qj5.7 harness, both with `priority=10`, different `node_id`s.
- Assert client picks one deterministically (lexicographic on `node_id`) when no other tiebreaker is set.
- Assert receipt carries the split-brain record.
- Set operator pin → assert pin wins.
- Bump epoch on the loser → assert epoch wins.
- Web-UI playwright: confirm yellow warning row + pin buttons function (route to bombadil).

### Out of scope (file separately)

- Multi-LAN federation collisions (different broadcast domains seeing each other via VPN).
- Cross-session reconciliation when two clients independently picked different sides.
- Automatic kill/STONITH — never appropriate on user hardware.

---

## Sources

1. Anantacloud — *Understanding the Split-Brain Scenario in etcd* — https://www.anantacloud.com/post/understanding-the-split-brain-scenario-in-etcd-for-devops-engineers
   etcd uses Raft term numbers + quorum heartbeats; partitioned leader steps down on losing quorum.
2. OneUptime — *How to Build Split-Brain Prevention* — https://oneuptime.com/blog/post/2026-01-30-split-brain-prevention/view
   Layered defenses: consensus quorum → fencing tokens → STONITH; ZK Zab + ≥3 odd nodes.
3. HashiCorp — *Identifying and Recovering from a Consul Split-Brain* — https://support.hashicorp.com/hc/en-us/articles/360058026733
   Symptoms: repeated elections, divergent member lists; cause: partitions or bad bootstrap.
4. Gaurav Sarma — *Split Brain in Distributed Databases* (2026-03) — https://www.gauravsarma.com/posts/2026-03-31_split-brain-in-distributed-databases
   Layered defense model: consensus → fencing tokens/leases → STONITH at storage.
5. RFC 6762 §9 — *Multicast DNS — Conflict Resolution* — https://datatracker.ietf.org/doc/html/rfc6762
   Probing (3× 250ms), lexicographic tiebreak on rdata, automatic rename on loss.
6. mdns-sd Rust crate docs — https://docs.rs/mdns-sd/latest/mdns_sd/
   Implements RFC 6762 §9; exposes conflict-event callbacks for application-level handling.
7. Server Fault — *How to prevent avahi from resolving mDNS name conflicts* — https://serverfault.com/questions/1149526/how-to-prevent-avahi-from-resolving-mdns-name-conflicts
   Avahi auto-renames to `-2` by default; this hides real conflicts and is sometimes disabled deliberately.
8. k8s client-go leaderelection — https://pkg.go.dev/k8s.io/client-go/tools/leaderelection
   Lease-based; renew interval + lease duration; designed for client-coordinated single-leader without state replication.
9. sklar.rocks — *Kubernetes-powered leader election in Go* — https://sklar.rocks/kubernetes-leader-election/
   Fencing tokens: monotonic int per lease handover; stale holders rejected at the sink.
10. Medium / Himanshu Gaur — *Zookeeper Split brain. What actually is Quorum?* — https://medium.com/@himanshugaur1215/zookeeper-split-brain-5c812b6a38d8
    Minority partition becomes unavailable; majority continues. CP-side of CAP.
11. Medium / Awinas — *Network Partition in Distributed Systems* — https://medium.com/@awinas270597/network-partition-in-distributed-systems-5a9dbe9a9173
    Cassandra/Dynamo gossip detection, AP side; Consul gossip-based service-discovery failure detection.
12. System Design Sandbox — *Leader Election* — https://www.systemdesignsandbox.com/learn/leader-election
    "Two-node leader election" anti-pattern: without quorum, both think the other is dead.

## Contested / Unclear

- **Auto-rename vs. surface-to-operator** is a real disagreement: mDNS RFC says auto-rename (silent); Avahi follows it; some operators explicitly disable it (Server Fault source 7) because it hides config errors. Saturn should *not* auto-rename services but *should* surface to operator — this is a deliberate departure from RFC 6762 §9 default behavior at the application layer (the responder still does name-uniqueness probing; we add a higher-level "two distinct identities, same priority" check).
- **Epoch-as-lease** is a Saturn-specific hint, not a standard pattern. Risk: clock skew between servers makes "newer" wrong. Documented as a hint that operator pin overrides — acceptable.

## Couldn't find

- A direct precedent for "client-side split-brain detection in a zero-config service-discovery system" — closest analogues are Bonjour-based apps (iTunes shared libraries, AirPlay receivers) but published implementation details are thin. Recommend treating Saturn's design here as novel and documenting it as such.
