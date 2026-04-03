# Administrator Guide

The administrator deploys Saturn, configures services, manages API credentials, and monitors health. One person bears this complexity so every user on the network gets a zero-config experience.

Running Saturn adds exactly two things to your infrastructure:

1. **One config file** — a TOML service definition per backend
2. **One background process** — the Saturn service proxy

This is a fixed cost amortized across every user on the network. Once Saturn is running, clients discover services automatically and route to the best available backend without touching a single config file or API key.

## What administrators manage

- **Backend selection** — which AI services to expose (Ollama, OpenRouter, DeepInfra, Claude, custom)
- **Priority assignment** — which backend gets traffic first, and the failover order
- **API credentials** — storing keys in environment variables, rotating beacon keys
- **Rate limiting** — per-IP and global request throttles
- **Remote access** — Cloudflare tunnels for off-network users
- **Health monitoring** — watching service status, responding to outages

## Guide contents

| Page | Description |
|------|-------------|
| [Router Setup](router-setup.md) | Deploying Saturn on an OpenWRT router |
| [Service Configuration](service-config.md) | Configuring backends with TOML files or the wizard |
| [Priority Routing](priority-routing.md) | How Saturn selects and fails over between services |
| [Rate Limiting](rate-limiting.md) | Throttling requests and filtering models |
| [Tunnels](tunnels.md) | Cloudflare tunnel setup for remote access |
| [Environment Variables](env-vars.md) | All runtime configuration variables |
| [Config TOML Reference](config-toml.md) | Schema tables for service TOML files |
| [CLI Reference](cli.md) | All administrator commands and flags |
