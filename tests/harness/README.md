# Saturn test harness

Real-Saturn primitives the hardener (and any chat-UX test loop) can call to
verify behavior against an actually-running Saturn server. **No mocks.**

Owner: `demo` crew (Saturn-qj5.7).

## Why

Hardener tests for chat-UX changes (qj5.1..qj5.6), the Configure split
(qj5.13), and the config→LLM proof suite (qj5.14) need to:

1. Spawn brand-new Saturn services (not just edit existing configs).
2. Discover them via mDNS / the Web UI.
3. Edit + verify edits propagate end-to-end.
4. Delete + verify removal.
5. Send real chat traffic to a real LLM (Ollama, or a keyed upstream).
6. Manage OpenRouter sub-keys for one-shot end-to-end runs without
   burning the parent key.

Bombadil already covers UI invariants. This harness covers the
Saturn-server side that Bombadil cannot see.

## Layout

| module | role |
| --- | --- |
| `service.py`  | install / edit / delete / start / stop / discover / endpoint |
| `chat.py`     | OpenAI-compatible POST helper |
| `web.py`      | `serve()` context manager — boots `saturn web` on a free port |
| `ollama.py`   | `ensure(model)` — daemon up + model pulled |
| `openrouter.py` | mgmt API (list / create / update / revoke sub-keys) |
| `playwright_example.py` | minimal browser flow as a copy-paste base |
| `selftest.py` | end-to-end smoke; CI gate for the harness itself |

## Invocation

Hardener tests should `import tests.harness` (the repo is the cwd) or
shell out via the CLI:

```sh
python3 -m tests.harness install demo-foo --priority 25
python3 -m tests.harness start  demo-foo
python3 -m tests.harness discover
python3 -m tests.harness chat --endpoint http://127.0.0.1:8080 \
    --model qwen2.5:0.5b --prompt 'hi' --max-tokens 16
python3 -m tests.harness edit   demo-foo --priority 10
python3 -m tests.harness stop   demo-foo
python3 -m tests.harness delete demo-foo

# OpenRouter mgmt
python3 -m tests.harness openrouter list
python3 -m tests.harness openrouter create selftest --limit 0.05
python3 -m tests.harness openrouter revoke <hash>
```

`OPENROUTER_PROVISIONING_KEY` is read from env or `.env` at the repo
root. Never commit `.env`.

## Python API (preferred for hardener tests)

```python
from tests.harness import chat, ollama, openrouter, service, web

ollama.ensure("qwen2.5:0.5b")

service.install("demo-foo", priority=25)
meta = service.start("demo-foo")          # {'pid', 'port', 'pidfile'}
ep   = f"http://127.0.0.1:{meta['port']}"

text, usage, raw = chat.reply(ep, "qwen2.5:0.5b", "hi", max_tokens=8)
assert usage["completion_tokens"] <= 8

with web.serve() as origin:                # ephemeral Saturn web UI
    # drive playwright against `origin` here
    pass

key = openrouter.create("one-shot", limit=0.05)
openrouter.revoke(key["data"]["hash"])

service.stop("demo-foo")
service.delete("demo-foo")
```

## Running the smoke test

```sh
set -a; source .env; set +a    # for the OpenRouter mgmt-API steps
python3 -m tests.harness.selftest
```

Expected tail:

```
[selftest] ALL OK
```

The smoke test exercises every primitive against a real Ollama daemon,
real mDNS, real Saturn server, and the real OpenRouter mgmt API
(creates + revokes a sub-key, no real spend).
