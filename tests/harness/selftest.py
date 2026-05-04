import sys
import time
import urllib.error
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
        step("install + start service @ priority 75 (no module → default runner)")
        service.install(NAME, priority=75)
        meta = service.start(NAME)
        expect(meta.get("port"), f"service registered (port={meta.get('port')})")
        expect(meta.get("token"), "runner token issued")

        step("discover")
        time.sleep(1.0)
        svcs = service.discover()
        match = [s for s in svcs if s["name"].startswith(NAME)]
        expect(match, f"service in mDNS browse ({[s['name'] for s in svcs]})")
        prio = match[0]["txt"].get("priority")
        expect(prio == "75", f"priority advertised as 75 (got {prio})")

        ep = f"http://127.0.0.1:{meta['port']}"

        step("auth gate: /v1/health 401 without bearer")
        try:
            chat.health(ep)
            expect(False, "expected 401 without bearer")
        except urllib.error.HTTPError as e:
            expect(e.code == 401, f"401 without bearer (got {e.code})")

        step("auth gate: /v1/health 401 with wrong bearer")
        try:
            chat.health(ep, token="wrong")
            expect(False, "expected 401 with wrong bearer")
        except urllib.error.HTTPError as e:
            expect(e.code == 401, f"401 with wrong bearer (got {e.code})")

        step("auth gate: /v1/health 200 with correct bearer")
        status, body = chat.health(ep, token=meta["token"])
        expect(status == 200 and body.get("status") == "ok",
               f"health ok with bearer (status={status}, body={body})")

        step("chat with bearer (max_tokens honored)")
        text, usage, _ = chat.reply(ep, MODEL, "Reply with exactly: ok.",
                                    token=meta["token"], max_tokens=8)
        expect(usage.get("completion_tokens", 99) <= 16,
               f"max_tokens honored ({usage})")

        step("edit -> priority 25, restart")
        service.stop(NAME)
        service.edit(NAME, priority=25)
        meta = service.start(NAME)
        time.sleep(1.0)
        svcs = service.discover()
        match = [s for s in svcs if s["name"].startswith(NAME)]
        expect(match and match[0]["txt"].get("priority") == "25",
               f"edit propagated (priority=25, got {match[0]['txt'].get('priority') if match else None})")

        step("web UI lifecycle + admin bearer")
        with web.serve() as srv:
            origin, admin_tok = srv["origin"], srv["token"]
            urllib.request.urlopen(origin, timeout=5).read()
            expect(True, f"web UI alive at {origin}")

            # /api/services 401 without bearer
            try:
                urllib.request.urlopen(f"{origin}/api/services", timeout=5).read()
                expect(False, "/api/services expected 401 without bearer")
            except urllib.error.HTTPError as e:
                expect(e.code == 401,
                       f"/api/services 401 without bearer (got {e.code})")

            # /api/services 200 with bearer
            status, body = web.admin_request(origin, "/api/services", admin_tok)
            expect(status == 200 and isinstance(body, list),
                   f"/api/services 200 with bearer ({len(body or [])} entries)")

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
