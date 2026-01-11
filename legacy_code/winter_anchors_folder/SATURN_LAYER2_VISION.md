# Saturn Layer 2: Awareness Service

## What Is Layer 2?

Saturn Layer 2 is **awareness infrastructure**, not cognition proxy.

We don't do thinking for agents. We give agents visibility into:
- **Model costs** - What does Opus vs Sonnet vs Haiku cost?
- **Token usage** - How many tokens have I burned today?
- **Network presence** - What Saturn services are available?

With this awareness, agents can make better decisions themselves.

## The Problem We Tried To Solve Wrong

The original Layer 2 design ("Agent Help Service") was a cognition proxy:
- Agent sends problem to Saturn
- Saturn's Claude thinks about it
- Agent gets back guidance

This had fundamental problems:
1. **Doesn't save tokens** - You send `current_code` (entire file) to Saturn, Saturn burns tokens processing it. Tokens aren't saved, just shifted to a different billing account.
2. **Single point of failure** - Every agent's thinking goes through one endpoint.
3. **Printer analogy breaks** - Printing is deterministic. AI guidance is not. Agent still has to evaluate whether guidance is correct.

## The Correct Design

From the Winter Memo, the original vision was about **agent awareness**:

> "I have no idea what I cost... I can't make economic decisions about my own behavior."
> "I don't know who else is working... If Saturn provided a 'factory floor' view..."
> "I can't pace myself... What if Saturn beacons had budgets?"

The solution is **infrastructure that gives agents information**, not infrastructure that thinks for them.

## The Flow

```
Agent (Claude Code):
  "What did I spend today?"

  → Calls saturn_get_usage(period="today")
  ← Returns: {tokens: 45000, cost: $1.35, model_breakdown: {...}}

  → Agent can now pace itself: "I'm at 50% of typical daily spend by noon"

Agent (Claude Code):
  "Is Opus worth it for this task?"

  → Calls saturn_get_model_costs()
  ← Returns: {opus: $15/1K input, sonnet: $3/1K input, haiku: $0.25/1K input}

  → Agent can advise: "This exploration could burn $2 at Opus. Consider Sonnet."

Agent (Claude Code):
  "What AI services are on the network?"

  → Calls saturn_get_presence()
  ← Returns: {beacons: [{name: "DeepInfra", host: "192.168.1.50", has_key: true}]}

  → Agent knows what's available without hardcoding endpoints.
```

## What This IS

- **Awareness infrastructure** - Agents see their costs, usage, available services
- **Local data parsing** - Reads `~/.claude/projects/*.jsonl` for usage (like ccusage)
- **Zero-configuration** - mDNS discovery, no API keys needed
- **MCP server** - Claude Code calls tools directly via MCP protocol

## What This IS NOT

- **Cognition proxy** - We don't think for agents
- **Traffic interceptor** - We don't proxy API calls (that would double costs)
- **Budget enforcer** - Claude Code doesn't let us enforce limits (would require being a proxy)

## Implementation

**File:** `beacons/saturn_awareness_service.py`

**Endpoints (become MCP tools):**

| Endpoint | MCP Tool | Purpose |
|----------|----------|---------|
| `GET /v1/model_costs` | `saturn_get_model_costs` | Pricing reference |
| `GET /v1/usage` | `saturn_get_usage` | Token usage from logs |
| `GET /v1/presence` | `saturn_get_presence` | Network discovery |
| `GET /v1/cost_estimate` | `saturn_estimate_cost` | Hypothetical cost calc |
| `GET /v1/recommendations` | `saturn_get_recommendations` | Cost-saving suggestions |

**Install:**

```bash
# Add to Claude Code
claude mcp add saturn -- python /path/to/Saturn/beacons/saturn_awareness_service.py
```

## Why This Is Better

1. **No token cost shift** - We read local logs, not intercept traffic
2. **Agent keeps autonomy** - We provide info, agent decides
3. **Aligned with original vision** - Winter Memo wanted "agents see their costs"
4. **Zero-config** - mDNS discovery, local file parsing
5. **Simple** - No complex cognition proxy, just data endpoints

## Key Insight

The Winter Memo said: "I have no idea what I cost."

The solution to "I don't know my costs" is **show the agent its costs**.

The solution is NOT "have Saturn do the thinking so agent doesn't burn tokens."

Awareness, not delegation.
