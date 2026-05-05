# BONJOUR_AVAHI_FACTS.md

> Answers to writer-bonjour-gaps.md (10 gaps). Cite sources; flag uncertainty.
> Feeds: docs/concepts/mdns-background.md, docs/platform-notes.md, README laptop-as-beacon section.

## Bonjour / macOS

### Gap #1 — Network Browser display of `_saturn._tcp.local.`
**Answer:** macOS Finder's "Network" sidebar only renders services it has special-cased (AFP, SMB, NFS, `_device-info._tcp`, `_adisk._tcp`, etc.); a generic `_saturn._tcp.local.` will NOT appear in Finder. It is fully visible to `dns-sd -B _saturn._tcp` and to `Discovery - DNS-SD Browser` (App Store) and `Bonjour Browser`. Instance names are rendered as published — UTF-8, with spaces and case preserved (`dns-sd` escapes spaces as `\032` in raw form but UI tools un-escape). On conflict mDNSResponder appends ` (2)`, ` (3)`, etc. (RFC 6762 §9 "Conflict Resolution" leaves the format implementation-defined; Apple's mDNSResponder uses the space-paren-N-paren convention).
**Sources:**
- https://www.synoforum.com/threads/how-to-fix-nas-visibility-in-macos-finder-sidebar.6903/ — Finder sidebar requires `_device-info._tcp` / `_adisk._tcp` flags; arbitrary services don't show
- https://datatracker.ietf.org/doc/html/rfc6762#section-9 — conflict-resolution rules; new name "MUST be deterministically generated" but format is up to implementation
**Caveat:** Finder invisibility is the rule, not the exception — don't promise "shows up in Finder" in landing copy.

### Gap #2 — `.local.` trailing dot
**Answer:** Both forms are equivalent in DNS (the trailing dot denotes the FQDN root). Apple's `dns-sd` and `mDNSResponder` accept either; published records are stored canonically with the dot internally. RFC 6762 §3 writes `.local.` consistently with the trailing dot to emphasize it is a top-level pseudo-TLD; Avahi documentation and CLI tools omit the dot (`avahi-publish -s foo _saturn._tcp 8080`). No functional difference.
**Sources:**
- https://datatracker.ietf.org/doc/html/rfc6762#section-3 — uses `.local.` form throughout
- `man dns-sd` (Apple) — examples shown both with and without trailing dot
**Caveat:** Recommend Saturn docs use `_saturn._tcp.local.` (with dot) to match RFC; tolerate both in parsers.

### Gap #3 — TXT cumulative size ceiling
**Answer:** RFC 6763 §6.1 caps each TXT *string* at 255 bytes and the entire TXT *record* (sum of strings) at 65535 bytes (DNS RDATA limit). RFC 6763 §6.2 gives the operational guidance Saturn cares about: keep TXT under 200 bytes for typical use, under 400 bytes to fit a single 512-byte DNS message, and **under 1300 bytes** to fit a single 1500-byte Ethernet frame (avoiding IP fragmentation). Above ~1300 bytes the responder must fragment or fall back to TCP, which many mDNS clients handle poorly. Apple does not document a hard ceiling below 65535, but mDNSResponder will warn in syslog above ~1300 bytes. The "1300 byte" chatter originates directly from RFC 6763 §6.2, not folklore.
**Sources:**
- https://datatracker.ietf.org/doc/html/rfc6763#section-6.2 — canonical 200/400/1300 byte tiers
- https://www.ietf.org/rfc/rfc6763.txt — "keeping the size of the TXT record under 1300 bytes should allow it to fit in a single 1500-byte Ethernet packet"
**Caveat:** Saturn TXT should aim for <400 bytes if `ephemeral_key` is included (Ed25519 pub key in base64 ~44 bytes leaves headroom); never exceed 1300.

### Gap #4 — Conflict-suffix format
**Answer:** RFC 6762 §9 mandates conflict resolution but leaves the renaming algorithm to implementations ("a programmatically generated replacement name"). Apple's mDNSResponder convention: append ` (2)` then increment — `ollama` → `ollama (2)` → `ollama (3)`. Avahi uses a hyphen: `ollama` → `ollama #2` → `ollama #3` (configurable in `avahi-daemon.conf`). The instance name in the wire-format SRV/TXT changes accordingly; clients see the rewritten name verbatim.
**Sources:**
- https://datatracker.ietf.org/doc/html/rfc6762#section-9 — conflict resolution semantics
- Apple `man mDNSResponder` and `dns-sd` source (mDNSCore/mDNS.c, `IncrementLabelSuffix`) — ` (N)` format
**Caveat:** Saturn's numeric-priority tiebreak should NOT depend on instance-name string equality. If two beacons publish `ollama`, one becomes `ollama (2)` and clients can no longer match on name. Match on TXT keys (e.g., `priority=`) instead.

### Gap #5 — Sleep Proxy + TXT updates [CORRECTNESS-CRITICAL]
**Answer:** Bonjour Sleep Proxy Service (SPS) **freezes the TXT record at the time of registration**. Before sleeping, mDNSResponder transfers its full record set (A, AAAA, SRV, PTR, TXT) to the sleep proxy via a DNS Update message (Cheshire's "DNS-SD Sleep Proxy" draft uses standard DNS Update wire format). The proxy then answers mDNS queries with those exact records until either (a) the host wakes and re-registers, or (b) the records' TTL expires and the proxy sends a goodbye. The proxy has no mechanism to receive TXT mutations from a sleeping host — the host is asleep, by definition. To rotate `ephemeral_key`, the sleeping Mac must wake (e.g., on a periodic `pmset` schedule or because of an incoming query that triggers wake-on-demand), re-register the new TXT, and sleep again.
**Sources:**
- https://stuartcheshire.org/sleepproxy/ — "SPS Registered ... My\032Sleeping\032Mac._ssh._tcp.local. SRV ... TXT" — full record set transferred at sleep, replayed verbatim by proxy
- https://en.wikipedia.org/wiki/Bonjour_Sleep_Proxy — "register its services with an available sleep proxy server" (one-shot at sleep time)
- https://datatracker.ietf.org/doc/draft-cheshire-edns0-owner-option/ — "DNS-SD Sleep Proxy Service uses a message format identical to that used by standard DNS Update" (no streaming update channel)
**Caveat — Saturn implication:** **For laptop-as-beacon deployments, ephemeral_key TTL must be longer than the sleep window OR the laptop must be configured to wake periodically to re-publish.** Recommended: (1) document that laptop beacons should disable App Nap / set `pmset -a sleep 0` while acting as beacon, OR (2) make `ephemeral_key` rotation cadence explicit and longer than typical idle sleep (e.g., 24h rotation, 1h max sleep). Do NOT assume readers behind an SPS will see live TXT updates.

## Avahi / Linux

### Gap #6 — Default subdomain confirmation
**Answer:** Avahi serves `.local` by default, configurable via `domain-name=` in `/etc/avahi/avahi-daemon.conf` (default: `local`). One-liner to confirm what the running daemon serves: `avahi-browse -d local -art` (browse all services in `local` domain, resolve, terminate). To confirm hostname resolution is wired through NSS: `getent hosts $(hostname).local` — if it returns an address, `nss-mdns` is installed and the `mdns4_minimal` (or `mdns_minimal`) hook is in `/etc/nsswitch.conf`. To dump the full effective config including all browse domains: `avahi-browse -D` (lists browsing domains).
**Sources:**
- `man avahi-daemon.conf` — `domain-name` directive, default `local`
- `man avahi-browse` — `-D` lists browse domains, `-d` selects one
- https://wiki.archlinux.org/title/Avahi — `getent hosts foo.local` confirmation pattern
**Caveat:** `mdns4_minimal` only resolves IPv4 `.local`; if Saturn responder advertises only AAAA and the host has `mdns4_minimal` (no `mdns6_minimal` or `mdns_minimal`), resolution silently fails. Document `nsswitch.conf` line for distros.

### Gap #7 — `avahi-publish` TXT escaping
**Answer:** `avahi-publish-service` takes TXT key=value pairs as separate trailing arguments — no shell-escaping of `=` is required *inside* a value because each TXT pair is its own argv element. The shell only needs quoting if a value contains spaces or shell metacharacters: `avahi-publish-service ollama _saturn._tcp 8080 "endpoint=https://1.2.3.4:443" "priority=10"`. Internally Avahi treats anything after the first `=` as the value (per RFC 6763 §6.4); literal `=` in values is fine. There is no documented Avahi-specific escaping requirement — the confusion stems from older `avahi-publish` (pre-0.7) which mis-parsed values starting with `-`.
**Sources:**
- `man avahi-publish-service` — argv layout for TXT pairs
- https://datatracker.ietf.org/doc/html/rfc6763#section-6.4 — "first '=' character is the delimiter"
- Avahi 0.8 source (`avahi-utils/avahi-publish.c`) — values passed through unchanged after first `=`
**Caveat:** Quote the whole `key=value` argument if value has spaces; never escape the `=` itself.

### Gap #8 — AP isolation + Avahi reflector
**Answer:** AP isolation (a.k.a. "client isolation" or "guest mode") drops L2 frames between wireless clients on the same AP, including multicast frames to `224.0.0.251:5353`. **No mDNS reflector — Avahi's `enable-reflector=yes`, dedicated tools like `mdns-repeater`, or commercial mDNS gateways — can defeat AP isolation by itself**, because the reflector listens on the wired/router side and clients can't reach it. Avahi's reflector mode bridges mDNS *between separate L2 segments* (e.g., VLAN A ↔ VLAN B) when running on a router/host with an interface in each. Defeating AP isolation requires disabling AP isolation at the AP, OR putting clients on a real bridged network. Treat the network as the trust boundary.
**Sources:**
- `man avahi-daemon.conf` — `enable-reflector`, `reflect-ipv` semantics: bridges between interfaces on the host
- https://github.com/lathiat/avahi/issues — multiple threads (e.g., #239, #313) confirming reflector requires multi-interface host, not a workaround for AP isolation
- https://wiki.archlinux.org/title/Avahi#Hostname_resolution_does_not_work_in_certain_applications — reflector use cases all involve multi-segment routing
**Caveat:** Saturn's "enterprise WiFi breaks discovery" warning is correct and unfixable from the responder side. Recommend a fallback to manual endpoint entry for AP-isolated networks.

## Cross-platform

### Gap #9 — Windows Bonjour Print Services + dns-sd.exe
**Answer:** Apple's **Bonjour Print Services for Windows v2.0.2** is the latest release (2014, Windows XP SP2 through Windows 10 — Apple has not officially blessed Win 11 but it installs and runs). The installer ships `mDNSResponder.exe` (the service) and `dns-sd.exe` (the CLI) reliably; `dns-sd.exe` is in `C:\Program Files\Bonjour\`. Apple has not formally deprecated BPS but has not updated it in 10+ years; it is in maintenance mode. Modern Windows 10/11 includes its own mDNS resolver (since 1809 / 2018) for hostname `.local` lookups, but it does NOT expose a DNS-SD browse CLI — the built-in stack resolves but does not enumerate. PowerShell `Resolve-DnsName -Name foo.local` works for hostname resolution but cannot browse `_saturn._tcp.local`. For Windows DNS-SD browsing, BPS (or Avahi-on-WSL, or third-party `dns-sd` ports like `mdns-tools`) remains the practical choice.
**Sources:**
- https://support.apple.com/en-us/106380 — current BPS download page (still v2.0.2)
- https://superuser.com/questions/1824603/what-happened-to-mdns-or-bonjour-do-i-need-it-anymore — Windows built-in mDNS resolves but doesn't browse
- https://learn.microsoft.com/en-us/answers/questions/5640645/what-is-bonjour-service-all-about-on-my-windows-11 — BPS still functional on Win 11
**Caveat:** BPS install is non-trivial (requires admin, installs a service); Saturn quickstart should warn and offer the WSL+Avahi alternative.

### Gap #10 — iOS / Android stock browsability
**Answer:** Yes — both platforms expose general DNS-SD browse APIs to apps:
- **iOS:** `NWBrowser` (Network framework, iOS 12+) or legacy `NetService` can browse arbitrary `_saturn._tcp` types. **iOS 14+ requires the app declare `NSLocalNetworkUsageDescription` and `NSBonjourServices` (with the explicit service type `_saturn._tcp`) in Info.plist, and the user must approve a Local Network permission prompt on first browse.** Without that, the browse silently returns no results.
- **Android:** `NsdManager` (since API 16) can browse any service type. No special manifest permission was required pre-Android 12; **Android 13+ (API 33) requires `NEARBY_WIFI_DEVICES` runtime permission for some discovery APIs**, though `NsdManager` itself is generally exempt for mDNS-only use. Stock browser apps (e.g., "Service Browser" on Play Store) work without Saturn-specific code.
- There is **no built-in OS-level UI** on either platform that browses arbitrary mDNS service types — apps must opt in.
**Sources:**
- https://developer.apple.com/documentation/network/nwbrowser — modern API
- https://developer.apple.com/news/?id=0oi77447 — iOS 14 local network permission requirement, mandatory `NSBonjourServices` allowlist
- https://developer.android.com/develop/connectivity/wifi/use-nsd — `NsdManager` overview
**Caveat:** Saturn cannot promise "any iPhone can browse" — requires a Saturn-aware (or general-purpose Bonjour browser) app; iOS additionally requires user permission grant.

## Saturn-actionable summary
- **Laptop-as-beacon (Gap #5):** Sleep Proxy freezes TXT. Either (a) keep beacon laptop awake (`pmset -a sleep 0` while beaconing), or (b) set `ephemeral_key` rotation cadence longer than the sleep window. Document this trade-off explicitly in the laptop-as-beacon section.
- **TXT budget (Gap #3):** Stay under 400 bytes total TXT for safe single-packet UDP; hard limit 1300 bytes for single Ethernet frame. RFC 6763 §6.2 is canonical.
- **Conflict resolution (Gap #4):** Don't tiebreak on instance-name equality — Bonjour rewrites to `ollama (2)`, Avahi to `ollama #2`. Match on TXT keys (`priority=`).
- **AP isolation (Gap #8):** Unfixable from the Saturn side. Document fallback to manual endpoint entry; do not promise reflector-based workarounds.
- **Cross-platform reach (Gaps #9, #10):** Windows needs Bonjour Print Services for CLI browsing; iOS needs `NSBonjourServices` + user permission; Android needs `NsdManager` (and a third-party browser app for users without Saturn). No platform offers a built-in mDNS service-type browser UI.

## Sources canvassed
- RFC 6762 (mDNS) §3, §9 — `.local.` form, conflict resolution
- RFC 6763 (DNS-SD) §6.1, §6.2, §6.4 — TXT size tiers, key=value parsing
- Stuart Cheshire, "Understanding Sleep Proxy Service" (stuartcheshire.org/sleepproxy) — SPS registration semantics
- `draft-cheshire-edns0-owner-option` — SPS uses DNS Update format (one-shot, not streaming)
- `man avahi-daemon.conf`, `man avahi-publish-service`, `man avahi-browse` — Avahi defaults and CLI shapes
- Apple `man dns-sd`, mDNSResponder source — `_(N)` conflict suffix convention
- Apple Support 106380 — Bonjour Print Services v2.0.2 current
- Apple developer docs — `NWBrowser`, iOS 14 local-network permission
- Android developer docs — `NsdManager`
- Wikipedia: Bonjour Sleep Proxy — corroboration on register-at-sleep flow
