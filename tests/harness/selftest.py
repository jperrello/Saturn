import sys
import time
import urllib.request

from . import chat, ollama, openrouter, service, web

NAME = "harness-selftest"
MODEL = "qwen2.5:0.5b"


def step(msg): print(f"\n[selftest] {msg}", flush=True)


def expect(cond, msg):
    if not cond: print(f"FAIL: {msg}"); sys.exit(1)
    print(f"OK: {msg}")


def main():
    step("preflight: ollama")
    ollama.ensure(MODEL)

    try:
        step("install + start service @ priority 75")
        service.install(NAME, priority=75)
        meta = service.start(NAME)
        expect(meta.get("port"), f"service registered (port={meta.get('port')})")

        step("discover")
        time.sleep(1.0)
        svcs = service.discover()
        match = [s for s in svcs if s["name"].startswith(NAME)]
        expect(match, f"service in mDNS browse ({[s['name'] for s in svcs]})")
        prio = match[0]["txt"].get("priority")
        expect(prio == "75", f"priority advertised as 75 (got {prio})")

        step("chat against running service")
        ep = f"http://127.0.0.1:{meta['port']}"
        text, usage, _ = chat.reply(ep, MODEL, "Reply with exactly: ok.", max_tokens=8)
        expect(usage.get("completion_tokens", 99) <= 16, f"max_tokens honored ({usage})")

        step("edit -> priority 25, restart")
        service.stop(NAME)
        service.edit(NAME, priority=25)
        service.start(NAME)
        time.sleep(1.0)
        svcs = service.discover()
        match = [s for s in svcs if s["name"].startswith(NAME)]
        expect(match and match[0]["txt"].get("priority") == "25",
               f"edit propagated (priority=25, got {match[0]['txt'].get('priority') if match else None})")

        step("web UI lifecycle")
        with web.serve() as origin:
            urllib.request.urlopen(origin, timeout=5).read()
            expect(True, f"web UI alive at {origin}")

    finally:
        step("cleanup service")
        service.stop(NAME)
        service.delete(NAME)

    step("openrouter mgmt API: list / create / revoke")
    keys = openrouter.list()
    expect(isinstance(keys, list), f"list returned {len(keys)} keys")
    sub = openrouter.create("saturn-harness-selftest", limit=0.05)
    h = sub.get("data", {}).get("hash") or sub.get("hash")
    expect(h, f"created subkey hash={h}")
    rev = openrouter.revoke(h)
    expect(rev is not None, "revoked subkey")

    print("\n[selftest] ALL OK")


if __name__ == "__main__":
    main()
