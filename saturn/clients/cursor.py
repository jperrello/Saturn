import argparse
import sys


SNIPPET = """\
Cursor — Saturn integration walkthrough
========================================

Saturn endpoint:  {base_url}

Cursor's "Override OpenAI Base URL" is GUI-only — there is no public
settings.json key for it (verified against Cursor 0.x docs + community
research, see dist/research/cursor_config.md). Follow these steps in the
Cursor IDE:

1. Open Settings (Cmd/Ctrl + ,).
2. Go to:  Settings > Models
3. Find the "OpenAI API Key" section. Click "Override OpenAI Base URL"
   and paste:
        {base_url}
4. Paste any non-empty string into the API Key field (Cursor does not
   validate it locally — it just attaches it as the Bearer token). E.g.
   "saturn-dummy" is fine.
5. Click "Add Model" / "Verify" and add the model id you want exposed.

REQUIRED — Ask mode, NOT Agent mode
-----------------------------------
Cursor's Agent mode emits Responses-API-shaped payloads to
/chat/completions and breaks against any pure Chat-Completions endpoint
(including Saturn's). You MUST use Ask mode for Saturn-routed traffic.
Switch via the chat composer's mode toggle (Ask / Agent).

REQUIRED — HTTP/1.1, NOT HTTP/2
-------------------------------
Cursor's custom-OpenAI client is incompatible with HTTP/2 upstreams.
In Cursor:
        Settings > Network > HTTP Compatibility Mode -> HTTP/1.1
Saturn itself speaks HTTP/1.1 by default; this flip is for Cursor's
internal client behaviour.

CAVEAT — subagents bypass the override
--------------------------------------
Subagent / background-task calls in Cursor bypass the "Override OpenAI
Base URL" setting and go straight to Cursor's hosted backend. Only the
main Ask-mode pane will route through Saturn. If you need every call
routed, wrap the model server upstream of Cursor instead.

References
----------
- Saturn research: dist/research/cursor_config.md (gullivan2)
- Saturn endpoints: `saturn endpoint`, `saturn discover --json`
"""


def render(base_url: str) -> str:
    return SNIPPET.format(base_url=base_url)


def _discover(timeout: float):
    from saturn.discovery import discover
    services = discover(timeout=timeout)
    openai = [s for s in services if s.api_type == "openai"]
    if not openai:
        return None
    openai.sort(key=lambda s: s.priority)
    return openai[0]


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="saturn cursor-snippet",
        description="Print a Cursor IDE walkthrough for using a Saturn endpoint as the Override OpenAI Base URL.",
    )
    p.add_argument("--base-url", default=None, help="Saturn /v1 endpoint URL (skip discovery).")
    p.add_argument("--timeout", type=float, default=5.0, help="Discovery timeout seconds (default 5.0).")
    args = p.parse_args(argv)

    if args.base_url:
        sys.stdout.write(render(args.base_url))
        return 0

    svc = _discover(args.timeout)
    if svc is None:
        print(
            "saturn cursor-snippet: no Saturn openai service found on the LAN.\n"
            "Hint: run `saturn endpoint` to verify discovery, or pass --base-url <url>.",
            file=sys.stderr,
        )
        return 1
    sys.stdout.write(render(svc.effective_endpoint))
    return 0
