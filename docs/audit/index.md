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
- [Hermes](hermes.md)
- [omlx](omlx.md)

## Results matrix

| Integration | Status | Last verified | Test file |
|---|---|---|---|
| Open WebUI | green (6/6, 2026-05-06) | 2026-05-06 (in-tree) | `tests/integrations/test_openwebui.py` |
| OpenCode | green (6/6, 2026-05-06) | 2026-05-06 (in-tree) | `tests/integrations/test_opencode.py` |
| Aider | green (7/7, 2026-05-06) | 2026-05-06 (in-tree) | `tests/integrations/test_aider.py` |
| Jan | green (6/6, 2026-05-06) | 2026-05-06 (in-tree) | `tests/integrations/test_jan.py` |
| VLC | green (9/9, 2026-05-06) | 2026-05-06 (in-tree) | `tests/integrations/test_vlc.py` |
| MCP | green (11/11, 2026-05-06) | 2026-05-06 (in-tree) | `tests/integrations/test_mcp.py` |
| Claude (server) | green (9/9, 2026-05-06) | 2026-05-06 (in-tree) | `tests/integrations/test_claude.py` |
| Claude (mount) | green (12/12, 2026-05-06) | 2026-05-06 (in-tree) | `tests/integrations/test_claudemount.py` |
| Ollama | green (8/8, 2026-05-06, real qwen2.5:0.5b) | 2026-05-06 (in-tree) | `tests/integrations/test_ollama.py` |
| Fallback | green (8/8, 2026-05-06) | 2026-05-06 (in-tree) | `tests/integrations/test_fallback.py` |
| OpenRouter | green 8/9, 1 SKIP live (no key) | 2026-05-06 (in-tree) | `tests/integrations/test_openrouter.py` |
| DeepInfra | green 7/8, 1 SKIP live (no key) | 2026-05-06 (in-tree) | `tests/integrations/test_deepinfra.py` |
| Cursor | snippet CLI green (9/9, 2026-05-06) | 2026-05-06 (gullivan2) | `tests/integrations/test_cursor.py` |
| Hermes | TBD (client integration, contract pivot in flight) | 2026-05-06 (geoff) | `tests/integrations/test_hermes.py` |
| omlx | proxy green (9/9, 2026-05-06) | 2026-05-06 | `tests/integrations/test_omlx.py` |
