"""
Saturn Awareness Service: Layer 2 MCP Server

Gives Claude Code agents visibility into:
- Model costs across providers (so agents can advise on cost-effective approaches)
- Token usage from local JSONL logs (parsed like ccusage)
- Network presence via mDNS (other Saturn services)

This is NOT a cognition proxy. It provides AWARENESS so agents can make
informed decisions about cost, pacing, and coordination.

Zero-configuration: Discovers Saturn beacons via mDNS.
Simple install: claude mcp add saturn -- python -m beacons.saturn_awareness_service

Based on ccusage (https://github.com/ryoppippi/ccusage) approach for JSONL parsing.

!!!!!!!!!!
THIS CODE IS UNFINISHED AND IS NOT INTEGRATED YET. THIS IS A LEGACY IDEA AND IS NOW BEING REPLACED WITH THE IDEA IN ~./research/rings!
!!!!!!!!!!
"""

from fastapi import FastAPI, Query
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import json
import re
import subprocess
import asyncio

app = FastAPI(
    title="Saturn Awareness Service",
    description="MCP server providing cost visibility and network awareness",
    version="0.1.0"
)

# Prices per 1K tokens in USD (updated Dec 2025)
MODEL_COSTS = {
    "anthropic": {
        "claude-opus-4": {"input": 15.00, "output": 75.00},
        "claude-opus-4-5-20251101": {"input": 15.00, "output": 75.00},
        "claude-sonnet-4": {"input": 3.00, "output": 15.00},
        "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
        "claude-haiku-3-5": {"input": 0.80, "output": 4.00},
        "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    },
    "deepinfra": {
        "meta-llama/Llama-3.3-70B-Instruct": {"input": 0.23, "output": 0.40},
        "Qwen/Qwen3-235B-A22B": {"input": 0.20, "output": 0.90},
        "microsoft/phi-4": {"input": 0.07, "output": 0.14},
        "deepseek-ai/DeepSeek-R1": {"input": 0.55, "output": 2.19},
    },
    "openrouter": {
        "anthropic/claude-sonnet-4": {"input": 3.00, "output": 15.00},
        "openai/gpt-4o": {"input": 2.50, "output": 10.00},
        "google/gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    }
}


@dataclass
class UsageStats:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    session_count: int = 0
    model_breakdown: Dict[str, Dict[str, int]] = field(default_factory=dict)


class JSONLParser:
    """
    Parse Claude Code's local JSONL files for usage data.
    Based on ccusage approach: https://github.com/ryoppippi/ccusage
    """

    def __init__(self, claude_dir: Optional[Path] = None):
        self.claude_dir = claude_dir or Path.home() / ".claude" / "projects"

    def find_jsonl_files(self, since: Optional[datetime] = None) -> List[Path]:
        if not self.claude_dir.exists():
            return []

        files = list(self.claude_dir.rglob("*.jsonl"))

        if since:
            files = [f for f in files if datetime.fromtimestamp(f.stat().st_mtime) > since]

        return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)

    def parse_file(self, file_path: Path) -> UsageStats:
        stats = UsageStats()

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        self._extract_usage(entry, stats)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

        return stats

    def _extract_usage(self, entry: dict, stats: UsageStats):
        # Claude Code stores usage in various locations depending on message type
        usage = None
        model = "unknown"

        # Check common locations for usage data
        if "usage" in entry:
            usage = entry["usage"]
            model = entry.get("model", "unknown")
        elif "message" in entry and isinstance(entry["message"], dict):
            if "usage" in entry["message"]:
                usage = entry["message"]["usage"]
                model = entry["message"].get("model", entry.get("model", "unknown"))

        if usage:
            input_t = usage.get("input_tokens", 0)
            output_t = usage.get("output_tokens", 0)
            cache_create = usage.get("cache_creation_input_tokens", 0)
            cache_read = usage.get("cache_read_input_tokens", 0)

            stats.input_tokens += input_t
            stats.output_tokens += output_t
            stats.cache_creation_tokens += cache_create
            stats.cache_read_tokens += cache_read

            # Track per-model breakdown
            if model not in stats.model_breakdown:
                stats.model_breakdown[model] = {"input": 0, "output": 0}
            stats.model_breakdown[model]["input"] += input_t
            stats.model_breakdown[model]["output"] += output_t

    def calculate_cost(self, stats: UsageStats) -> float:
        total_cost = 0.0

        for model, tokens in stats.model_breakdown.items():
            pricing = self._find_pricing(model)
            if pricing:
                cost = (tokens["input"] * pricing["input"] / 1000) + \
                       (tokens["output"] * pricing["output"] / 1000)
                total_cost += cost

        return total_cost

    def _find_pricing(self, model: str) -> Optional[Dict[str, float]]:
        # Direct match
        for provider, models in MODEL_COSTS.items():
            if model in models:
                return models[model]

        # Partial match (e.g., "claude-sonnet-4" matches "claude-sonnet-4-20250514")
        for provider, models in MODEL_COSTS.items():
            for model_name, pricing in models.items():
                if model_name in model or model in model_name:
                    return pricing

        return None

    def get_usage(self, period: str = "today") -> UsageStats:
        now = datetime.now()

        period_map = {
            "session": timedelta(hours=1),
            "today": now - now.replace(hour=0, minute=0, second=0, microsecond=0),
            "week": timedelta(days=7),
            "month": timedelta(days=30),
        }

        if period == "today":
            since = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period in period_map:
            since = now - period_map[period]
        else:
            since = None

        files = self.find_jsonl_files(since)

        total_stats = UsageStats()
        total_stats.session_count = len(files)

        for file_path in files:
            file_stats = self.parse_file(file_path)
            total_stats.input_tokens += file_stats.input_tokens
            total_stats.output_tokens += file_stats.output_tokens
            total_stats.cache_creation_tokens += file_stats.cache_creation_tokens
            total_stats.cache_read_tokens += file_stats.cache_read_tokens

            for model, tokens in file_stats.model_breakdown.items():
                if model not in total_stats.model_breakdown:
                    total_stats.model_breakdown[model] = {"input": 0, "output": 0}
                total_stats.model_breakdown[model]["input"] += tokens["input"]
                total_stats.model_breakdown[model]["output"] += tokens["output"]

        total_stats.total_tokens = total_stats.input_tokens + total_stats.output_tokens
        total_stats.estimated_cost_usd = self.calculate_cost(total_stats)

        return total_stats


class NetworkDiscovery:
    """Discover Saturn services on the network via mDNS (dns-sd)."""

    @staticmethod
    async def discover_services(timeout: float = 2.0) -> List[Dict[str, Any]]:
        services = []

        try:
            proc = await asyncio.create_subprocess_exec(
                "dns-sd", "-B", "_saturn._tcp", "local",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            await asyncio.sleep(timeout)
            proc.terminate()

            stdout, _ = await proc.communicate()
            output = stdout.decode()

            service_names = []
            for line in output.split('\n'):
                if 'Add' in line and '_saturn._tcp' in line:
                    parts = line.split()
                    if len(parts) >= 7:
                        service_names.append(parts[6])

            for name in service_names[:10]:  # Limit to prevent slowness
                info = await NetworkDiscovery._lookup_service(name)
                if info:
                    services.append(info)

        except FileNotFoundError:
            # dns-sd not available (Linux without Avahi, etc.)
            pass
        except Exception:
            pass

        return services

    @staticmethod
    async def _lookup_service(name: str) -> Optional[Dict[str, Any]]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "dns-sd", "-L", name, "_saturn._tcp", "local",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            await asyncio.sleep(1.5)
            proc.terminate()

            stdout, _ = await proc.communicate()
            output = stdout.decode()

            for line in output.split('\n'):
                if 'can be reached at' in line:
                    match = re.search(r'(\S+):(\d+)', line)
                    if match:
                        host = match.group(1).rstrip('.')
                        port = int(match.group(2))

                        txt = {}
                        for item in re.findall(r'(\w+)=([^\s]+)', output):
                            txt[item[0]] = item[1]

                        return {
                            "name": name,
                            "host": host,
                            "port": port,
                            "url": f"http://{host}:{port}",
                            "priority": int(txt.get("priority", 999)),
                            "version": txt.get("version", "unknown"),
                            "api": txt.get("api", "openai"),
                            "has_ephemeral_key": "ephemeral_key" in txt or "key" in txt,
                        }
        except Exception:
            pass

        return None


# Singleton parser instance
_parser = JSONLParser()


# === API ENDPOINTS (become MCP tools via fastapi_mcp) ===

@app.get("/v1/model_costs")
async def get_model_costs(provider: Optional[str] = None) -> Dict:
    """
    Get model pricing data. Prices are per 1K tokens in USD.

    Use this to understand cost tradeoffs:
    - Opus: $15 input / $75 output - most capable, use for complex reasoning
    - Sonnet: $3 input / $15 output - balanced, good for most tasks
    - Haiku: $0.80 input / $4 output - fast and cheap, good for simple tasks
    - DeepInfra Llama: $0.23 input - very cheap for exploration
    """
    if provider:
        return {"provider": provider, "models": MODEL_COSTS.get(provider, {})}
    return {"providers": MODEL_COSTS}


@app.get("/v1/usage")
async def get_usage(
    period: str = Query("today", description="One of: session, today, week, month, all")
) -> Dict:
    """
    Get your token usage from local Claude Code logs (~/.claude/projects/*.jsonl).

    Returns token counts, estimated cost, and per-model breakdown.
    Use this to understand your spending patterns and pace yourself.
    """
    stats = _parser.get_usage(period)
    return {
        "period": period,
        "input_tokens": stats.input_tokens,
        "output_tokens": stats.output_tokens,
        "cache_creation_tokens": stats.cache_creation_tokens,
        "cache_read_tokens": stats.cache_read_tokens,
        "total_tokens": stats.total_tokens,
        "estimated_cost_usd": round(stats.estimated_cost_usd, 4),
        "session_count": stats.session_count,
        "model_breakdown": stats.model_breakdown,
    }


@app.get("/v1/presence")
async def get_presence() -> Dict:
    """
    Discover Saturn services on the local network via mDNS.

    Shows available AI backends, beacons with ephemeral keys, etc.
    Use this to understand what resources are available.
    """
    services = await NetworkDiscovery.discover_services()

    # Categorize services
    beacons = [s for s in services if s.get("has_ephemeral_key")]
    servers = [s for s in services if not s.get("has_ephemeral_key")]

    return {
        "discovered_at": datetime.now().isoformat(),
        "beacon_count": len(beacons),
        "server_count": len(servers),
        "beacons": beacons,
        "servers": servers,
    }


@app.get("/v1/cost_estimate")
async def estimate_cost(
    input_tokens: int = Query(..., description="Expected input tokens"),
    output_tokens: int = Query(..., description="Expected output tokens"),
    model: str = Query("claude-sonnet-4", description="Model to price")
) -> Dict:
    """
    Estimate cost for a hypothetical request.

    Use this before expensive operations to decide if it's worth the cost.
    Example: "This 50K token context will cost ~$0.15 with Sonnet, ~$0.75 with Opus"
    """
    pricing = _parser._find_pricing(model)

    if pricing:
        cost = (input_tokens * pricing["input"] / 1000) + \
               (output_tokens * pricing["output"] / 1000)
        return {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost_usd": round(cost, 4),
            "pricing_per_1k": pricing,
        }

    return {
        "model": model,
        "error": f"Pricing not found for '{model}'",
        "available_models": [m for p in MODEL_COSTS.values() for m in p.keys()],
    }


@app.get("/v1/recommendations")
async def get_recommendations() -> Dict:
    """
    Get cost-saving recommendations based on your usage patterns.

    Analyzes recent usage and suggests optimizations like:
    - Switch to Haiku for simple tasks
    - Use Sonnet for exploration, Opus only for synthesis
    - Pace yourself if spending too fast
    """
    today = _parser.get_usage("today")
    week = _parser.get_usage("week")

    recommendations = []

    # Check Opus usage
    opus_input = sum(
        tokens.get("input", 0)
        for model, tokens in today.model_breakdown.items()
        if "opus" in model.lower()
    )
    total_input = today.input_tokens or 1

    if opus_input / total_input > 0.5:
        recommendations.append({
            "type": "cost_optimization",
            "severity": "high",
            "message": f"Opus is {opus_input/total_input*100:.0f}% of today's input. "
                      f"Consider Sonnet for research, Opus only for final synthesis.",
        })

    # Budget warning
    if today.estimated_cost_usd > 10:
        recommendations.append({
            "type": "budget_warning",
            "severity": "medium",
            "message": f"Today's cost: ${today.estimated_cost_usd:.2f}. Consider pacing.",
        })

    # Daily average
    if week.session_count > 0:
        daily_avg = week.estimated_cost_usd / 7
        if today.estimated_cost_usd > daily_avg * 2:
            recommendations.append({
                "type": "pace_warning",
                "severity": "medium",
                "message": f"Today (${today.estimated_cost_usd:.2f}) is 2x your daily avg (${daily_avg:.2f}).",
            })

    if not recommendations:
        recommendations.append({
            "type": "info",
            "severity": "low",
            "message": "Usage looks good. No immediate recommendations.",
        })

    return {
        "today": {
            "tokens": today.total_tokens,
            "cost_usd": round(today.estimated_cost_usd, 4),
        },
        "week": {
            "tokens": week.total_tokens,
            "cost_usd": round(week.estimated_cost_usd, 4),
        },
        "recommendations": recommendations,
    }


@app.get("/v1/health")
async def health() -> Dict:
    """Health check endpoint."""
    claude_dir = Path.home() / ".claude" / "projects"
    return {
        "status": "ok",
        "claude_logs_found": claude_dir.exists(),
        "service": "saturn-awareness",
        "version": "0.1.0",
    }


# === MCP INTEGRATION ===

def setup_mcp():
    try:
        from fastapi_mcp import FastApiMCP
        mcp = FastApiMCP(app)
        mcp.mount_http()
        return True
    except ImportError:
        return False


# Try to set up MCP (non-blocking if not installed)
_mcp_available = setup_mcp()


def main():
    """Run the Saturn Awareness Service."""
    import uvicorn

    print("Saturn Awareness Service")
    print("=" * 40)
    print(f"MCP available: {_mcp_available}")
    print(f"Claude logs: {Path.home() / '.claude' / 'projects'}")
    print()
    print("Endpoints:")
    print("  GET /v1/model_costs    - Model pricing reference")
    print("  GET /v1/usage          - Your token usage from logs")
    print("  GET /v1/presence       - Saturn services on network")
    print("  GET /v1/cost_estimate  - Estimate cost for tokens")
    print("  GET /v1/recommendations - Cost-saving suggestions")
    print()
    if _mcp_available:
        print("MCP server available at /mcp")
    else:
        print("Install fastapi-mcp for MCP support: pip install fastapi-mcp")
    print()

    uvicorn.run(app, host="127.0.0.1", port=8090)


if __name__ == "__main__":
    main()
