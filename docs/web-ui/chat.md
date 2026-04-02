# Chat

The Chat tab is the primary interface for interacting with AI models discovered on the Saturn network.

## Service and Model Selection

Two dropdowns at the top of the chat panel control routing:

- **Service** — pick a specific backend (Ollama, LM Studio, etc.) or select **Auto-route (Brutus)** for automatic backend selection based on priority and availability.
- **Model** — lists models available on the selected service. When auto-route is active, models from all services are shown.

## Model Favorites

Star any model to pin it to the top of the model dropdown. Click the star icon next to a model name to toggle. Favorites persist in localStorage.

## Streaming and Rendering

Responses stream token-by-token via SSE. The chat renders:

- Full **Markdown** (headings, lists, tables, links, images)
- **Code blocks** with syntax highlighting and a copy button
- Inline code and LaTeX

## Thinking Mode

Cycle through thinking modes by clicking the thinking toggle:

**Off** &rarr; **On** &rarr; **Deep** &rarr; **Off**

When enabled, the model's chain-of-thought reasoning appears in a collapsible block above the final response. Deep mode requests extended reasoning (higher token budget for the thinking step).

## File Attachments

Drag and drop files onto the chat input, or click the attachment icon.

| Supported types | Max size |
|-----------------|----------|
| `.txt` `.md` `.py` `.js` `.ts` `.json` `.toml` `.yaml` `.csv` | 100 KB |

Attached file contents are injected into the prompt context.

## Response Styles

A dropdown next to the input lets you set the response style:

- **Default** — standard model behavior
- **Concise** — shorter, direct answers
- **Detailed** — longer, thorough explanations
- **Code** — prioritize code output with minimal prose

The style is applied as a system-level instruction.

## Chat History

The sidebar lists up to **50 conversations**, sorted by recency. Each conversation is auto-named from its first message. Click any entry to resume it.

### Export

Export the current conversation from the sidebar menu:

- **JSON** — structured message array with metadata
- **Markdown** — formatted transcript

## Context Window Management

A token budget bar appears below the model dropdown, visualizing usage from 0--100%.

- At **80%**, a warning badge appears.
- When the budget is exceeded, **auto-compact** trims the oldest messages from context to stay within the model's limit.

This keeps conversations running without manual intervention. The compacted messages remain visible in the chat UI but are grayed out to indicate they are no longer in the active context.

## Welcome Screen

New conversations show a welcome screen with quick example prompts:

```
"Explain quantum computing in simple terms"
"Write a Python function to merge two sorted lists"
"Compare REST and GraphQL"
```

Click any prompt to send it immediately.
