# Saturn Beacon (Embedded)

Minimal mDNS beacon for OpenWRT routers. Announces Saturn credentials via DNS-SD
so devices on the local network can discover and use ephemeral API keys.

## Quick Start (GL-MT300N-V2 Mango)

```bash
# Build for MIPS
CGO_ENABLED=0 GOOS=linux GOARCH=mipsle GOMIPS=softfloat \
  go build -ldflags "-s -w" -o saturn-beacon ./cmd/saturn-beacon/

# Optional: Compress with UPX (reduces ~7MB -> ~2-3MB)
upx --best saturn-beacon

# Copy to router (use tmpfs for testing)
scp saturn-beacon root@192.168.8.1:/tmp/

# SSH and run
ssh root@192.168.8.1
DEEPINFRA_API_KEY=your-key-here /tmp/saturn-beacon
```

## Binary Size

| Stage | Size |
|-------|------|
| Uncompressed | ~7.0 MB |
| After UPX | ~2.5 MB (estimated) |
| Target | <3 MB |

The router has limited flash (1.5MB available) but tmpfs has ~60MB.
For Phase 1 testing, run from /tmp. Phase 2 will create a proper .ipk package.

## Configuration

Create `/tmp/beacon.json`:

```json
{
  "name": "mango-beacon",
  "priority": 10,
  "provider": {
    "type": "deepinfra",
    "api_key": "your-deepinfra-api-key",
    "rotation_seconds": 300,
    "expires_seconds": 600
  }
}
```

Or use environment variables / flags:

```bash
# Via environment
DEEPINFRA_API_KEY=your-key /tmp/saturn-beacon

# Via flags
/tmp/saturn-beacon --api-key=your-key --priority=10

# With config file
/tmp/saturn-beacon --config=/tmp/beacon.json
```

## Verification

From your laptop on the same network:

```bash
# macOS/Linux - browse for Saturn services
dns-sd -B _saturn._tcp local.

# Lookup specific service (get TXT records)
dns-sd -L mango-beacon _saturn._tcp local.
```

Expected TXT records:
- `version=1.0`
- `api=DeepInfra`
- `api_base=https://api.deepinfra.com/v1/openai`
- `priority=10`
- `ephemeral_key=eyJ...` (rotates every 5 minutes)
- `rotation_interval=300`
- `features=ephemeral_auth`

## Resource Usage

Target constraints:
- RAM: <15 MB (router has ~70 MB available)
- CPU: Minimal (only active during rotation)

Monitor on router:
```bash
top -bn1 | grep saturn
```

## Architecture

```
┌─────────────────────────────────────────┐
│           OpenWRT Router                │
│                                         │
│  saturn-beacon                          │
│    │                                    │
│    ├─► DeepInfra Provider               │
│    │     └─► Generate JWT               │
│    │                                    │
│    └─► mDNS Announcer                   │
│          └─► TXT records with           │
│              ephemeral credentials      │
└─────────────────────────────────────────┘
         │
         │ mDNS multicast
         ▼
┌─────────────────────────────────────────┐
│     Devices on Local Network            │
│                                         │
│  • Claude Code discovers beacon         │
│  • Gets ephemeral JWT from TXT          │
│  • Calls DeepInfra directly             │
└─────────────────────────────────────────┘
```

Traffic never flows through the router. The beacon only broadcasts credentials.

## Supported Providers

Currently: **DeepInfra** only (Phase E1)

Future phases will add:
- OpenRouter
- Anthropic
- OpenAI

## Related Files

- `beacon.example.json` - Sample configuration
- `../../internal/providers/` - Provider implementations
- `../../internal/providers/deepinfra.go` - DeepInfra JWT generation

## Troubleshooting

**"mDNS registration failed"**
- Check if avahi-daemon or another mDNS responder is running
- Try a different service name with `--config`

**"Failed to generate credential"**
- Verify API key is correct
- Check network connectivity to api.deepinfra.com

**High memory usage**
- Shouldn't happen with this minimal binary
- Check with `cat /proc/$(pidof saturn-beacon)/status | grep VmRSS`
