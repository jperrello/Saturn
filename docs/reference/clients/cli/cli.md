# CLI Reference

All commands are invoked as `saturn <command> [options]`.

## `saturn discover`

Discover all Saturn services on the local network.

```bash
saturn discover
saturn discover --json
saturn discover --timeout 10
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--timeout` | float | `5.0` | Discovery timeout in seconds |
| `--json` | flag | off | Output in JSON format |

## `saturn endpoint`

Print the best available service endpoint URL. Useful for scripts and piping.

```bash
saturn endpoint
saturn endpoint --json
export OPENAI_BASE_URL=$(saturn endpoint)
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--timeout` | float | `5.0` | Discovery timeout in seconds |
| `--json` | flag | off | Output in JSON format |

## `saturn run <name>`

Start a configured service by name.

```bash
saturn run openrouter
saturn run ollama --port 8080
saturn run deepinfra --host 127.0.0.1
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `name` | positional | -- | Service name (from `~/.saturn/services/` or built-in) |
| `--host` | string | `0.0.0.0` | Host to bind to |
| `--port` | int | auto | Port to bind to (auto-assigns if not specified) |
| `--list` / `-l` | flag | off | List available services |

## `saturn stop <name>`

Stop a running Saturn service.

```bash
saturn stop openrouter
```

| Argument | Description |
|----------|-------------|
| `name` | Name of the service to stop |

## `saturn config list`

List all configured services (built-in and user-created).

```bash
saturn config list
```

## `saturn config new`

Interactive wizard to create a new service configuration. Prompts for name, API type, upstream URL, API key environment variable, and other settings.

```bash
saturn config new
```

## `saturn config delete <name>`

Delete a user-created service configuration.

```bash
saturn config delete myservice
saturn config delete myservice --force
```

| Flag | Description |
|------|-------------|
| `--force` / `-f` | Stop the service first if it's currently running |

## `saturn web`

Launch the Saturn Web UI.

```bash
saturn web
saturn web --port 8080
saturn web --host 127.0.0.1 --port 3000
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--host` | string | `0.0.0.0` | Host to bind to |
| `--port` | int | `3000` | Port to bind to |

## `saturn aider`

Launch Aider with auto-discovered Saturn service.

```bash
saturn aider
saturn aider --select
saturn aider --saturn-model gpt-4
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--select` | flag | off | Interactively select server and model |
| `--saturn-model` | string | -- | Use a specific model (skips selection) |
| `--saturn-needs` | string | -- | Required capabilities, comma-separated |
| `--saturn-min-context` | int | `0` | Minimum context window size |
| `--saturn-prefer-free` / `--no-saturn-prefer-free` | flag | on | Prefer free services |
| `--saturn-verbose` | flag | off | Show discovery details |
| `--timeout` | float | `8.0` | Discovery timeout in seconds |

Unrecognized arguments are passed through to Aider.

## Service shortcuts

Any configured service name can be used directly as a command:

```bash
saturn ollama           # same as: saturn run ollama
saturn openrouter       # same as: saturn run openrouter
saturn deepinfra        # same as: saturn run deepinfra
```

Run `saturn --help` to see all available service shortcuts.
