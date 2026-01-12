# Saturn Beacons

This directory contains Saturn beacon and awareness service implementations.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 2: Awareness Service (saturn_awareness_service.py)        │
│                                                                 │
│ MCP server giving Claude Code agents visibility into:          │
│ - Model costs (pricing reference)                              │
│ - Token usage (parsed from ~/.claude/projects/*.jsonl)         │
│ - Network presence (mDNS discovery)                            │
│                                                                 │
│ NOT a proxy. Provides AWARENESS so agents can decide better.   │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 1: DeepInfra Beacon (winter_beacon.py)                    │
│                                                                 │
│ mDNS credential dispenser:                                      │
│ - Generates scoped JWT from DeepInfra API                      │
│ - Embeds in TXT record (ephemeral_key=...)                     │
│ - Rotates every 5 minutes                                       │
│                                                                 │
│ Clients call DeepInfra DIRECTLY with extracted key.            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Layer 1: DeepInfra Beacon

### How It Works

1. Beacon generates a scoped JWT from DeepInfra API (expires in 10 minutes)
2. JWT is embedded in mDNS TXT record under `ephemeral_key`
3. Beacon announces itself as `_saturn._tcp.local.` service
4. Clients discover beacon via mDNS and extract ephemeral key
5. Clients call DeepInfra API **DIRECTLY** using the key (not through beacon)
6. Every 5 minutes, beacon rotates to a new JWT

### Running the Beacon

```bash
export DEEPINFRA_API_KEY="your_api_key_here"
pip install zeroconf requests python-dotenv

python beacons/winter_beacon.py --port 8090 --priority 10
```

### Verify via mDNS

```bash
dns-sd -B _saturn._tcp local
dns-sd -L DeepInfra-Beacon _saturn._tcp local
```

---

## Layer 2: Awareness Service

### What It Does

An MCP server that gives Claude Code agents visibility into:

| Endpoint | Purpose |
|----------|---------|
| `/v1/model_costs` | Pricing per 1K tokens for Opus/Sonnet/Haiku/DeepInfra |
| `/v1/usage` | Token usage from local logs (today/week/month) |
| `/v1/presence` | Saturn beacons and servers on the network |
| `/v1/cost_estimate` | Calculate cost for hypothetical request |
| `/v1/recommendations` | Cost-saving suggestions based on patterns |

### Installation

**Option 1: Add to Claude Code as MCP server**

```bash
claude mcp add saturn -- python /path/to/Saturn/beacons/saturn_awareness_service.py
```

Or manually add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "saturn": {
      "command": "python",
      "args": ["/path/to/Saturn/beacons/saturn_awareness_service.py"]
    }
  }
}
```

**Option 2: Run as HTTP server**

```bash
pip install fastapi uvicorn fastapi-mcp
python beacons/saturn_awareness_service.py
```

Server runs at `http://127.0.0.1:8090`. MCP endpoint at `/mcp`.

### Example Agent Behavior

With awareness data, an agent can:

1. **Advise on model selection**: "This research task could burn ~$2 at Opus rates. Consider Sonnet for exploration."

2. **Pace itself**: "You've used 45K tokens today ($1.35). At this rate, you'll hit typical daily spend by 3pm."

3. **Know what's available**: "Found 2 Saturn beacons on the network: one with DeepInfra, one with OpenRouter."

### Design Philosophy

This is **awareness infrastructure**, not cognition proxy:
- We don't do the thinking for agents
- We give agents information so they can make better decisions
- We don't intercept traffic (that would double costs)
- We read local logs that Claude Code already writes

---

## Security Model

**Beacon (Layer 1):**
- Credentials expire automatically after 10 minutes
- New credentials generated every 5 minutes
- Leave network = lose access (mDNS is local-only)
- No long-lived credentials stored on clients

**Awareness Service (Layer 2):**
- Runs locally, no external API calls for cost data
- Reads only local Claude logs (no network data exfiltration)
- mDNS discovery is read-only network scan

---

## File Structure

| File | Layer | Purpose |
|------|-------|---------|
| `winter_beacon.py` | 1 | DeepInfra JWT beacon with mDNS announcement |
| `saturn_awareness_service.py` | 2 | MCP server for cost/usage/presence awareness |

---

## Troubleshooting

**Beacon won't start:**
- Ensure `DEEPINFRA_API_KEY` is set
- Verify zeroconf and requests libraries installed

**Awareness service can't find logs:**
- Check `~/.claude/projects/` exists
- Ensure Claude Code has been used (creates logs on first use)

**MCP tools not appearing in Claude Code:**
- Verify `fastapi-mcp` is installed: `pip install fastapi-mcp`
- Check settings.json path is correct
- Restart Claude Code after config changes
