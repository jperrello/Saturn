# cbt.5 — AP-isolation reproduction notes

True AP (access-point) isolation cannot be simulated end-to-end on a single
loopback host: it is a Layer-2 / firewall property of the wireless network
itself. The router blocks station-to-station traffic, so multicast (224.0.0.251
/ ff02::fb on UDP 5353) silently fails to reach peers even though the local
host happily transmits and receives its own packets.

We document **two** flavours of reproduction:

  (1) operator-grade: a real isolated network, used for end-to-end demos and
      the LANDING_DEMO capture.
  (2) developer-grade: a software simulation of the *symptoms* the detector
      sees, used by automated tests and by anyone without access to a guest
      Wi-Fi.

## (1) Operator-grade reproduction

Pick any AP-isolated network. UCSC reference networks (per RUN_BRIEF_MAY03
§6.1.2): `eduroam`, `UCSC-Guest`. Home reference: most "Guest" SSIDs on
consumer routers default to client isolation = on.

Two-host steps:

  1. Connect host A and host B to the same AP-isolated SSID.
  2. On host A:  `saturn web --port 8080 &`
                 `saturn services add demo-a --priority 10`
  3. On host B:  `saturn web --port 8080 &`
                 Open the Web-UI Network Scan tab.
  4. Expect: host B's scan **does not** discover host A despite both being on
     the same SSID. Confirm with: `dns-sd -B _saturn._tcp.` on host B (no
     hits).
  5. Switch one host to a non-isolated SSID (home Wi-Fi or hotspot). Re-run.
     Both should now discover each other.

This is the canonical "AP isolation" environment. The detector's job is to
recognise this state and surface it in the Web-UI.

## (2) Developer-grade simulation

We can simulate the **symptoms** locally by selectively dropping inbound mDNS
traffic from the loopback peer. Two approaches:

### 2a. macOS pf rule (requires sudo)

```sh
# Block inbound mDNS from a specific peer port to simulate "we advertise, they
# don't see us" — does not require leaving the host.
echo "block in proto udp from 127.0.0.1 to 224.0.0.251 port 5353" \
  | sudo pfctl -ef -
# revert:
sudo pfctl -d
```

### 2b. In-process fault injection (the path the test suite uses)

`saturn/mdns/userspace.py::UserspaceBackend` already has the seam: pass a
`fault_filter` that drops `ServiceEvent`s matching a predicate. The detector
checks two signals:

  - **advertise-but-blind**: we hold a registration with `state=announced`,
    yet `discover()` returns 0 services for >N seconds (default 8s) AND
    `socket.if_indextoname(...)` reports we're on a Wi-Fi interface whose
    SSID matches a known-isolated allowlist OR we observe inbound mDNS
    queries we cannot answer (peers asking for `_saturn._tcp.local.` while
    we have nothing to show them).
  - **browse-but-empty-with-known-peers**: known_nodes.json (qj5.7j3) lists
    peers but `discover()` finds none of them for >N seconds.

When either signal latches, the detector sets `W._network_state =
"ap_isolated"` and the Web-UI `Network Scan` tab renders a yellow banner
linking to `/configure?manual=1`.

## Falsifiable acceptance (for hardener)

  - `saturn.mdns.detect.ap_isolated() -> bool` returns True under simulation
    (2b) within 8s of the first failed discover round.
  - `/api/system/network/scan` response includes
    `{"network_state": "ap_isolated", "advice_url": "/configure?manual=1"}`
    when the detector has latched.
  - Web-UI Network Scan tab renders the yellow banner with a clickable
    "Switch to manual configuration" link (rodney capture required).
  - When run on a non-isolated network, the detector stays at `"ok"` for at
     least 30 seconds with at least one peer present.

## Demo capture plan

Once the detector lands, capture two stills via `rodney`:

  - `cbt.5-ap-isolated.png` — Web-UI Network Scan tab on the isolated SSID,
    yellow banner visible, manual-config link rendered.
  - `cbt.5-ok.png` — same tab on a healthy network, scan results populated.

The operator-grade path requires the user (or the demo recorder) to be on
campus / on a guest network. The developer-grade simulation suffices for
green CI; mark the rodney capture as "in_progress" in LANDING_DEMO.md until a
real isolated-network capture is available.
