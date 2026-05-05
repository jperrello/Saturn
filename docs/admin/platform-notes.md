# Platform notes — what works where

This page is for the person deploying Saturn for other people. It documents what each client OS does (and doesn't do) with `_saturn._tcp.local.` discovery, so you can pick a posture that doesn't quietly fail for half your users.

Companion pages: [`docs/admin/security.md`](security.md) for the trust posture decision matrix; [`docs/admin/configure.md`](configure.md) for the runtime controls; [`docs/concepts/mdns-background.md`](../concepts/mdns-background.md) for the protocol-level "why". Sourcing for everything below: `BONJOUR_AVAHI_FACTS.md` at the repo root.

---

## At a glance

| Client | Browse `_saturn._tcp`? | What you have to do |
|---|---|---|
| **macOS** | Yes (CLI + third-party browsers; not Finder) | Nothing special. `dns-sd -B _saturn._tcp` works out of the box. |
| **Linux (Avahi)** | Yes | Install `avahi-daemon` + `nss-mdns`; verify `nsswitch.conf`. |
| **Windows 10/11** | Yes, but only with **Bonjour Print Services 2.0.2** installed (or WSL+Avahi). | The built-in resolver resolves `*.local` hostnames but cannot enumerate service types. |
| **iOS 14+** | Yes, only from a Saturn-aware app or general-purpose Bonjour browser. | App must declare `NSLocalNetworkUsageDescription` + `NSBonjourServices` with `_saturn._tcp` listed; user grants permission on first browse. |
| **Android (≥ API 16)** | Yes from any app using `NsdManager`. | No manifest permission for mDNS-only on most versions; Android 13+ may require `NEARBY_WIFI_DEVICES` for some discovery APIs. |

No platform ships a built-in OS-level UI that browses arbitrary mDNS service types. A Saturn-aware client (or a general-purpose browser app) is always required. Don't promise "any phone can browse" in user-facing copy.

---

## macOS

`mDNSResponder` is always running. Browse from a terminal:

```bash
dns-sd -B _saturn._tcp
dns-sd -L "<instance>" _saturn._tcp local.
```

GUI browsers that work: **Discovery — DNS-SD Browser** (App Store) and **Bonjour Browser**. Finder's "Network" sidebar **does not** render `_saturn._tcp.local.` — it special-cases AFP, SMB, NFS, `_device-info._tcp`, `_adisk._tcp`, and a handful of others. Saturn services exist, but Finder won't show them; tell users to use the Saturn client app.

Conflict-suffix shape on macOS: `ollama` → `ollama (2)` → `ollama (3)` (space, paren, N, paren — `IncrementLabelSuffix` in mDNSCore). Don't write client logic that filters on instance-name string equality; match on TXT keys (e.g. `priority=`).

### Laptop-as-beacon

If you run a beacon on a laptop, the Bonjour Sleep Proxy Service can keep replaying your TXT record after the laptop sleeps. The proxy receives a one-shot DNS Update at sleep time and serves those records verbatim until the host wakes — there is no streaming channel back from a sleeping host, so credential rotations during sleep don't propagate.

Two safe configurations:

1. **Always-on host.** Desktop, NAS, Raspberry Pi, lab server. This is what beacon mode is designed for.
2. **Laptop, kept awake while beaconing.** `caffeinate -i saturn run <name>`. Saturn offers to do this for you on first run via the Configure page A.8 power-mgmt opt-in (qj5.16.14, in flight).

Or align the rotation cadence with the longest plausible sleep window — 24 h rotation against 1 h max sleep is reasonable, 5 min rotation is not.

The full protocol-level explanation is in [`mdns-background.md`](../concepts/mdns-background.md#addendum-bonjour-sleep-proxy-and-beacon-hosts).

---

## Linux

Saturn assumes `avahi-daemon` plus `nss-mdns`. Install per distro:

```bash
# Debian/Ubuntu
sudo apt install avahi-daemon libnss-mdns
# Arch
sudo pacman -S avahi nss-mdns
# Fedora
sudo dnf install avahi nss-mdns
```

Confirm the daemon is serving the right domain and the resolver is wired:

```bash
avahi-browse -d local -art          # what does the daemon serve?
avahi-browse -D                     # which browse domains are active?
getent hosts $(hostname).local      # is NSS wired through mDNS?
```

`/etc/nsswitch.conf` should contain `mdns_minimal [NOTFOUND=return]` (or `mdns4_minimal` / `mdns6_minimal`) on the `hosts:` line, before `dns`. If you only have `mdns4_minimal` and Saturn responders are advertising AAAA-only, resolution silently fails — add `mdns6_minimal` or use the unified `mdns_minimal`.

Conflict-suffix shape on Avahi: `ollama` → `ollama-2` → `ollama-3` (hyphen-N — applied to both hostnames and service-instance names). Different shape from macOS; same caveat — match on TXT keys, not instance-name equality.

### Recent: Debian + systemd-resolved

systemd-resolved on recent Debian-family distros disables mDNS by default. If you see `getent hosts foo.local` returning empty on a host with the daemon running, check `resolvectl mdns` — flip it to `yes` per interface (`resolvectl mdns <iface> yes`) or stick with the avahi-only path. Detail in [`mdns-background.md` §9](../concepts/mdns-background.md).

### `avahi-publish` quoting

If you publish manually for testing: each TXT pair is its own argv element, so `=` inside a value needs no escaping. Quote the whole `key=value` argument when the value has spaces or shell metacharacters:

```bash
avahi-publish-service ollama _saturn._tcp 8080 \
  "endpoint=https://1.2.3.4:443" "priority=10"
```

Don't escape the `=` itself.

---

## Windows

The story splits in two: hostname resolution and service-type browsing.

### Hostname resolution — built-in, since 1809

Windows 10 (1809, October 2018) and Windows 11 ship a built-in mDNS resolver. `*.local` lookups work out of the box:

```powershell
Resolve-DnsName -Name saturn-host.local
ping saturn-host.local
```

No install needed. If a Saturn client knows the instance hostname (e.g. from configuration), it resolves and connects.

### Service-type browsing — needs Bonjour Print Services or WSL

The built-in resolver does **not** enumerate service types. There is no PowerShell cmdlet that browses `_saturn._tcp.local.` from a stock Windows install. Two practical options:

1. **Bonjour Print Services for Windows 2.0.2** — Apple's redistributable. Installs `mDNSResponder.exe` (service) and `dns-sd.exe` (CLI) into `C:\Program Files\Bonjour\`. Released 2014, no updates since, but Apple's support page still lists it as current and it installs and runs on Windows 11. Requires admin to install. After install:

   ```powershell
   & "C:\Program Files\Bonjour\dns-sd.exe" -B _saturn._tcp
   ```

   Source: <https://support.apple.com/en-us/106380>.

2. **WSL + Avahi.** If users already run WSL2 with a Linux distro, install `avahi-utils` inside the distro and use `avahi-browse`. Networking interop is good enough for browsing on the LAN.

If your user base includes Windows clients that aren't running a Saturn client app, document one of these paths in the install guide. The Saturn quickstart should warn that BPS install is non-trivial (admin, system service) and offer the WSL alternative.

Conflict-suffix shape on Windows: BPS uses Apple's `(N)` form. The built-in resolver does not register services, so this only applies if Windows hosts are publishing Saturn services via BPS.

---

## iOS

`NWBrowser` (Network framework, iOS 12+) and the legacy `NetService` API can browse arbitrary `_saturn._tcp` types. **iOS 14+ adds two structural gates:**

1. The app's `Info.plist` must declare:
   - `NSLocalNetworkUsageDescription` — a human-readable reason string.
   - `NSBonjourServices` — an explicit allowlist of service types the app is willing to browse. **Saturn-aware apps must list `_saturn._tcp` here.** A type not on the list is unbrowseable; the OS does not gracefully fall back, the call silently returns no results.
2. The user must approve a one-time Local Network permission prompt on first browse. Decline = no results, with no error surfaced to the app.

There is no system UI that browses arbitrary mDNS service types. Users need either a Saturn-aware app or a general-purpose Bonjour browser app from the App Store. As an admin, the implication for documentation: don't promise iPhones can find Saturn services unless a Saturn iOS client (or a Bonjour browser app) is installed and granted Local Network permission.

Source: <https://developer.apple.com/news/?id=0oi77447>; <https://developer.apple.com/documentation/network/nwbrowser>.

---

## Android

`NsdManager` (Network Service Discovery) has been available since API 16 (Android 4.1). It can browse any service type. No manifest permission was required pre-Android 12 for mDNS-only use.

Android 13 (API 33) introduced `NEARBY_WIFI_DEVICES` as a runtime permission for some discovery APIs. `NsdManager` itself is generally exempt for pure mDNS, but apps targeting newer SDK levels should test on a current device — Google has been tightening discovery permissions release over release.

Stock browser apps from the Play Store ("Service Browser" and similar) work without Saturn-specific code or special permissions on most Android versions, which gives users a debug path that doesn't require installing a Saturn client first.

Source: <https://developer.android.com/develop/connectivity/wifi/use-nsd>.

---

## AP isolation breaks discovery on every platform

This isn't a per-OS issue — it's a network-level one — but it's the single most common reason "discovery doesn't work" reports come in.

AP isolation (also called "client isolation" or "guest mode") drops L2 frames between wireless clients on the same access point, including multicast frames to `224.0.0.251:5353`. **No mDNS reflector defeats this from the Saturn side.** Avahi `enable-reflector=yes`, `mdns-repeater`, and commercial mDNS gateways all bridge between separate L2 segments on a multi-interface host — they don't bridge clients that can't reach each other on the same segment.

Common deployments where AP isolation is on by default and discovery silently fails:

- Hotel and café WiFi.
- Most "guest network" SSIDs on consumer routers.
- Many enterprise/campus WiFi deployments.

Two real options:

1. **Disable AP isolation at the AP** (only feasible on networks you control).
2. **Manual endpoint entry.** Saturn clients should always allow typing in a hostname/port directly when discovery returns nothing. Document this as the universal fallback.

Reflector configurations that *do* work — bridging VLAN A ↔ VLAN B on a router with an interface in each — are documented in [`mdns-background.md`](../concepts/mdns-background.md). They are not a workaround for guest-mode WiFi.

---

## Cross-references

- [`docs/admin/security.md`](security.md) — trust posture per network type.
- [`docs/admin/configure.md`](configure.md) — runtime controls (Configure page).
- [`docs/concepts/mdns-background.md`](../concepts/mdns-background.md) — protocol-level detail; "Field gotchas (Bonjour vs Avahi)" addendum has the wire-level facts.
- `BONJOUR_AVAHI_FACTS.md` (repo root) — full citation set behind every claim on this page.
