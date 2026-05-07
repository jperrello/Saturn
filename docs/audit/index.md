# Saturn Ecosystem Audit

This directory contains a per-integration audit of every client and backend Saturn currently claims to support, plus the new integrations introduced in this run.

## Contents

- [Open WebUI](openwebui.md)
- [OpenCode](opencode.md)
- [Aider](aider.md)
- [Jan](jan.md)
- [VLC](vlc.md)
- [MCP](mcp.md)
- [Claude](claude.md)
- [Ollama](ollama.md)
- [Fallback](fallback.md)
- [OpenRouter](openrouter.md)
- [DeepInfra](deepinfra.md)
- [Cursor](cursor.md)
- [omlx](omlx.md)

## Considered backends

- [Hermes (NousResearch)](hermes.md) — surveyed, rejected: no
  OpenAI-compatible HTTP surface. Run Nous-trained weights behind vLLM /
  llama.cpp / SGLang / Ollama and advertise that.

## Results matrix

| Integration | Status | Last verified | Test file |
|---|---|---|---|
| Open WebUI | TBD | 2026-04-24 (geoff facts) | `tests/integrations/test_openwebui.py` |
| OpenCode | TBD | 2026-05-07 (geoff facts) | `tests/integrations/test_opencode.py` |
| Aider | TBD | 2026-04-25 (geoff facts) | `tests/integrations/test_aider.py` |
| Jan | TBD | 2026-03-23 (geoff facts) | `tests/integrations/test_jan.py` |
| VLC | TBD | 2026-05-06 (in-tree) | `tests/integrations/test_vlc.py` |
| MCP | TBD | 2026-05-06 (in-tree) | `tests/integrations/test_mcp.py` |
| Claude | TBD | 2026-05-06 (in-tree) | `tests/integrations/test_claude.py` |
| Ollama | TBD | 2026-05-06 (in-tree) | `tests/integrations/test_ollama.py` |
| Fallback | TBD | 2026-05-06 (in-tree) | `tests/integrations/test_fallback.py` |
| OpenRouter | TBD | TBD | `tests/integrations/test_openrouter.py` |
| DeepInfra | TBD | TBD | `tests/integrations/test_deepinfra.py` |
| Cursor | TBD | TBD | `tests/integrations/test_cursor.py` |
| Hermes | rejected | 2026-05-06 | — (no `/v1/*` surface) |
| omlx | TBD | TBD | `tests/integrations/test_omlx.py` |
