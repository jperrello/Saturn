# Writer — Bonjour / Avahi facts I'd like before final pass

Open. Non-blocking for the rough README; matters for the full pass on
docs/concepts/mdns-background.md and any "platform notes" sections.

## Bonjour / macOS

1. **Network Browser display.** When a Saturn responder publishes
   `_saturn._tcp.local.`, what (if anything) shows up in macOS Finder's
   "Network" sidebar or in `dns-sd -B` interactive output? Specifically:
   does the user-facing instance name (`ollama`) get rendered as-is, or
   does Bonjour rewrite it (capitalization, conflict suffixing like
   "ollama (2)")?

2. **`.local.` trailing dot.** `dns-sd` accepts both `local.` and `local`.
   Is there a documented Apple preference for which to publish with? Avahi
   examples in the wild are inconsistent.

3. **TXT key length vs string length.** RFC 6763 §6.1 caps each TXT
   *string* at 255 bytes. Apple's `dns-sd` further imposes practical
   limits on the *cumulative* TXT (~1300 bytes per the chatter) — does
   Apple document a hard ceiling, and does it fire before mDNS message
   fragmentation kicks in?

4. **Service-name conflict resolution.** When two responders publish the
   same instance name, Bonjour appends a discriminator (typically " (2)").
   Is the discriminator format documented? Saturn currently relies on
   numeric-priority-based conflict avoidance; if Bonjour rewrites the
   name, our priority-tiebreak logic could see surprising instance names.

5. **Sleep-proxy interaction.** macOS Bonjour Sleep Proxy can answer for
   sleeping advertisers. Does it forward TXT updates (`ephemeral_key`
   rotation) or freeze the last-seen TXT until the host wakes? This is
   load-bearing for cloud beacons running on a sleeping laptop.

## Avahi / Linux

6. **Default subdomain.** Avahi serves `.local` by default; some distros
   ship with `mdns4_minimal` only (no IPv6). Is there a one-liner to
   confirm a host's effective Avahi domain set?

7. **`avahi-publish` TXT escaping.** Some Avahi versions require shell-
   escaping `=` inside TXT values when published from CLI. Documented?
   Affects our quickstart's `avahi-publish` example.

8. **AP isolation behavior.** README cites that enterprise WiFi (AP
   isolation) breaks Saturn. Avahi has a `disable-publishing` setting
   and several reflector modes — is there a reflector mode that survives
   AP isolation, or is the network always the trust boundary?

## Cross-platform

9. **Windows + Bonjour Print Services.** Saturn quickstart tells Windows
   users to install BPS. Does BPS ship `dns-sd.exe` reliably across
   Windows 10/11 builds, or is it stripped from some installers? Has
   Apple deprecated BPS?

10. **iOS / Android browsability.** A Saturn responder on the LAN — can
    a stock iOS or Android client (no Saturn-aware app) browse it via
    standard Bonjour/NSD APIs? If yes, this is worth a one-liner in the
    landing copy.

## Severity

If only one of these is answered, prioritize **#5 (sleep-proxy +
ephemeral key rotation)** — it's a correctness question for a concrete
deployment we describe in the README (laptop-as-beacon).

The rest are documentation-completeness asks.
