# Models and Parameters

## All Models

The Models view aggregates every model from every discovered service into a single searchable list. Use the search bar to filter by name.

## Favorites and Aliases

Star a model to pin it in the chat dropdown. You can also create **aliases** — short names that map to a specific service/model pair:

```
@fast  →  ollama/llama3
@smart →  lmstudio/deepseek-r1
```

Aliases are usable in the model dropdown search.

## Manual Endpoints

Add backends that are not auto-discovered. Click **Add Endpoint** and provide:

| Field | Description |
|-------|-------------|
| Name | Display name for the service |
| URL | Base URL (e.g., `http://192.168.1.50:11434`) |
| API type | `openai`, `ollama`, or `anthropic` |

Manual endpoints appear alongside discovered services.

## Settings Overlay

Click the gear icon on any model or service to open the settings overlay. Settings have two scopes:

- **Global** — applies to all services unless overridden
- **Per-service** — overrides global for a specific backend

### Sampling Parameters

| Parameter | Range | Default |
|-----------|-------|---------|
| `temperature` | 0.0 -- 2.0 | 0.7 |
| `max_tokens` | 1 -- model max | 4096 |
| `top_p` | 0.0 -- 1.0 | 1.0 |
| `top_k` | 1 -- 500 | 40 |
| `frequency_penalty` | -2.0 -- 2.0 | 0.0 |
| `presence_penalty` | -2.0 -- 2.0 | 0.0 |
| `seed` | integer | — |

### Stop Sequences

Add one or more strings that cause the model to stop generating. Enter each sequence and press Enter to add.

### System Prompt

Set a system prompt at global or per-service scope. The per-service prompt fully replaces the global one when set.

```
You are a helpful coding assistant. Always include type annotations.
```

### Response Format

Choose between:

- **Text** — default free-form output
- **JSON schema** — paste a JSON schema to constrain model output to that structure

## Ollama-Specific Parameters

When an Ollama service is selected, additional parameters are available:

| Parameter | Description |
|-----------|-------------|
| `keep_alive` | How long to keep the model loaded after last use (e.g., `5m`, `24h`) |
| `mirostat` | Mirostat sampling mode (0 = disabled, 1, 2) |
| `repeat_penalty` | Penalty for repeated tokens (1.0 = none) |
| `repeat_last_n` | Lookback window for repeat penalty |
| `min_p` | Minimum probability threshold |
| `tfs_z` | Tail-free sampling parameter |
| `typical_p` | Locally typical sampling threshold |
| `num_ctx` | Context window size in tokens |
| `num_batch` | Batch size for prompt processing |
