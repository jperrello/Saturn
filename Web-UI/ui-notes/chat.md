# Chat Page

AI chat interface. Two-column layout with sidebar and main area.

## Sidebar
- Heading: "History"
- **"New Chat" button** at the top — creates a fresh conversation
- List of previous chats (truncated to 20 chars), named by first message
- Default items: "Python", "how to..", "Schedule.."
- Clicking a chat loads its full message history

### Chat Behavior
- All messages within a conversation stay in one chat — each message does NOT create a new chat
- A new chat is only created when the user clicks "New Chat"

## Main Area

### Top Bar
Two labeled selectors and a settings button:
- **Service selector**: labeled `Saturn Service: <selected>` (e.g. `Saturn Service: Derrick_LLMBuffet`). Options: Derrick_LLMBuffet, OpenRouter, OLLAMA
- **Model selector**: labeled `Model: <selected>` (e.g. `Model: Claude Sonnet 3.5`). Options: Claude Sonnet 3.5, GPT-4, Llama 3
- **Saturn logo button** (top right): small SVG image of Saturn (planet with rings) — no text, just the icon. Replaces the old `[CFG]` button. No handler yet.

### Messages Container
Initially shows a welcome screen:
- Prompt: "> How can I help today?"
- Three quick example buttons: "What is Saturn?", "Help me write an email", "Lets make a web page"

Clicking an example auto-fills input and sends. Welcome hides after first message.

Message format:
- **User**: prefix "> you" + bubble with escaped text
- **Assistant**: meta line "service // model" + optional tool indicators + bubble

### Tool Indicators
If user message contains `@`, the response shows tool badges:
- `READ <filename>` (extracts word after @)
- `WRITE`

### Input Area
- Text input with `> ` placeholder
- Send button
- Enter key also sends

## Mock Response Logic
- Message contains "saturn" -> Saturn description
- Message contains "@" -> "I've read the file and made the requested changes."
- Default -> "I can help with that. What details do you need?"

Response appears after 800ms delay.

## Reference Images
- `references/04-chat.jpeg` (welcome state)
- `references/05-chat-active.jpeg` (active conversation)
