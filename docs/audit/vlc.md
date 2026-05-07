# VLC

## Status
TBD (works | bit-rotted | broken)

## 2026-verified install
First-party Saturn extensions, shipped from this repo at `vlc_extension/`:

- `saturn_chat.lua` — interactive media-aware chat.
- `saturn_roast.lua` — comedic-roast extension (200-token cap on output).
- `vlc_discovery_bridge.py` — Python/FastAPI bridge (PyInstaller-bundled
  binaries in `vlc_extension/bridge/`).

The user copies the extension directory into VLC's extensions folder and
activates the extension under `View → Extensions` (`vlc_extension/README.md`,
"How It Works"). The bundled bridge executable removes the requirement that
the user have Python installed.

## How it points at Saturn

Two-layer architecture
(`docs/integrations/vlc.md`, `vlc_extension/README.md`):

1. **Lua extension** (`vlc_extension/saturn_roast.lua`,
   `vlc_extension/saturn_chat.lua`). Runs inside VLC. Provides the in-player
   GUI: service dropdown, action button, HTML output panel. Default bridge
   URL `http://127.0.0.1:9876` (`saturn_roast.lua:23`).
2. **Python/FastAPI bridge** (`vlc_extension/vlc_discovery_bridge.py`).
   Background process. Exposes an OpenAI-compatible REST API on localhost
   plus a `/services` route. Default port range starts at `9876`
   (`vlc_discovery_bridge.py:530`, `find_port_number(start_port=9876)`).

Discovery and request flow:

1. The Lua extension launches the bridge with `--port-file <path>`
   (`vlc_discovery_bridge.py:581`). The bridge auto-detects a free port,
   starts the HTTP server, and writes `host:port` to the port file.
2. The Lua extension polls the port file and health-checks with exponential
   backoff (7 retries, ~7 seconds total).
3. The Lua extension queries `/services` to populate the dropdown. The
   bridge browses `_saturn._tcp.local.` every 10 seconds via
   `dns-sd -B _saturn._tcp local` and resolves each instance with
   `dns-sd -L <instance> _saturn._tcp local.`
   (`vlc_discovery_bridge.py:119, :146`).
4. On user action, the extension extracts media context (title, artist,
   playback position), URL-encodes the payload as a `GET` query string, and
   sends it to the bridge. The bridge proxies to the selected service's
   `/v1/chat/completions`
   (`vlc_discovery_bridge.py:434, :451, :496`).
5. On extension deactivation the Lua side issues `/shutdown`; the bridge
   exits.

Saturn integration is **inverted** for VLC: the Saturn discovery client *is*
the bridge that VLC talks to over loopback. There is no patch into VLC core
— the integration is a pair of Saturn-shipped extension files plus a
PyInstaller-bundled binary.

## Known issues

VLC's Lua scripting environment imposes two structural constraints
(`docs/integrations/vlc.md`, "Trade-offs"):

- **No HTTP POST.** `vlc.stream()` issues GET requests only. Payloads ride
  on the URL-encoded query string with a 2048-character ceiling, which caps
  the size of any prompt or media-context payload sent from Lua to the
  bridge.
- **No JSON library.** VLC ships no JSON parser; the Lua extension carries a
  hand-written recursive-descent JSON parser.

Discovery requires `dns-sd` on the path (macOS Bonjour by default; Windows
needs Bonjour Print Services, see `BONJOUR_AVAHI_FACTS.md` Gap #9). On
hosts without `dns-sd`, the bridge logs *"dns-sd command not found - ensure
Bonjour/mDNS is installed"*
(`vlc_discovery_bridge.py:196`) and returns an empty service list.

## Test
See `tests/integrations/test_vlc.py`.

<!-- bombadil: results table goes here -->

| Scenario | Result | Notes |
|---|---|---|
| TBD | TBD | TBD |
