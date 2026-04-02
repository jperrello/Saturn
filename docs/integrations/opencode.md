# OpenCode

[OpenCode](https://github.com/anomaly/opencode) is an open-source terminal-based coding agent by Anomaly. Saturn was integrated via a fork that adds `ai-sdk-provider-saturn` as a bundled provider.

## How it works

The Saturn loader discovers services on the local network, fetches `/v1/models` from each, and registers every model as a dynamic provider. The model selector shows entries like `saturn:office/gpt-4o` — populated at runtime via mDNS, not hardcoded.

### Dynamic registration

When a service appears on the network, the loader calls `registerDynamic()` to make its models available. When a service disappears, `unregisterDynamic()` removes them. This happens continuously in the background.

```
onServiceDiscovered → registerDynamic()
onServiceRemoved   → unregisterDynamic()
```

### Capabilities

- Full agentic tool calling support (file edit, shell commands) over streaming connections
- Failover: if a service goes down mid-session, traffic reroutes to another available service
- Model selector updates live as services join and leave the network

## Integration scope

12 files modified across 4 packages. None of OpenCode's core abstractions were changed — Saturn plugs in through the existing provider interface.

## Source

[github.com/jperrello/Saturn](https://github.com/jperrello/Saturn/tree/main)
