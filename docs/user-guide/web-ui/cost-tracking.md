# Cost Tracking

The Web UI tracks token usage and estimated costs for API-backed models.

## Pricing Database

Saturn includes pricing data for 20+ models covering OpenAI, Anthropic, Google, and common open-weight models served through paid APIs. Prices are stored as cost per million tokens (input and output separately).

Local models (Ollama, LM Studio) report zero cost.

## Per-Message Cost

After each response, a small cost badge appears below the message showing:

- Input tokens used
- Output tokens used
- Estimated cost (e.g., `$0.003`)

Token counts are read from the API response headers or body when available.

## Daily Spend

The settings overlay shows a **Budget** section with:

| Metric | Description |
|--------|-------------|
| Today's spend | Sum of all message costs since midnight (local time) |
| Total spend | Cumulative across all sessions |
| Daily limit | Configurable cap (default: unlimited) |

Both daily and total spend are stored in localStorage.

## Spend Limit

Set a daily spend limit in the settings overlay. When the limit is reached:

1. A warning banner appears at the top of the chat
2. New messages are **blocked** until the next day or the limit is raised
3. The send button is disabled with a tooltip explaining why

```
Daily spend limit reached ($5.00 / $5.00). Reset at midnight or increase your limit in settings.
```

!!! tip
    Set a limit before using expensive models (GPT-4o, Claude Opus) to avoid surprise costs on metered API keys.

## Budget Summary

The budget summary in settings shows a breakdown:

- Per-model spend for the current day
- A bar chart of daily spend over the last 7 days
- The configured limit with a progress indicator
