import sys


HELP = """\
Saturn: Zero-configuration AI service discovery

Usage: saturn <command> [options]

Commands:
  discover              Discover Saturn services on the network
    --timeout <secs>      Discovery timeout (default: 5.0)
    --json                Machine-readable JSON output
  endpoint              Output best service endpoint URL
    --timeout <secs>      Discovery timeout (default: 5.0)
    --json                Machine-readable JSON output
  run <name>            Run a configured service
    --host <addr>         Host to bind to (default: 0.0.0.0)
    --port <port>         Port to bind to (default: auto)
  stop <name>           Stop a running service
  config list           List all configured services
  config new            Create a new service (interactive)
  config delete <name>  Delete a user service configuration
    --force               Stop the service first if running
  aider                 Launch Aider with auto-discovered Saturn service

Examples:
  saturn discover             Find services on the network
  saturn endpoint             Print best endpoint URL
  saturn run openrouter       Start the OpenRouter proxy
  saturn stop openrouter      Stop it
  saturn config list          Show all services
  saturn config new           Create a new service
  saturn config delete myservice   Delete a user config
  saturn ollama               Shortcut for 'saturn run ollama'
"""


def help():
    print(HELP.rstrip())
    print()
    print("Shortcuts (alias for 'saturn run <name>'):")
    from .config import list_service_configs
    for name, cfg, _ in list_service_configs():
        beacon = " [beacon]" if cfg.beacon.enabled else ""
        print(f"  {name:<22}{cfg.api_type} @ {cfg.upstream.base_url or '(self-contained)'}{beacon}")
    return 0


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help', 'help'):
        return help()

    command = sys.argv[1]
    remaining = sys.argv[2:]

    if command in ('discover', 'endpoint'):
        sys.argv = ['saturn', command] + remaining
        from .discovery import main as discovery_main
        return discovery_main()

    if command == 'config':
        sys.argv = ['saturn-config'] + remaining
        from .config import main as config_main
        return config_main()

    if command == 'run':
        sys.argv = ['saturn-run'] + remaining
        from .runner import main as runner_main
        return runner_main()

    if command == 'stop':
        if not remaining:
            print("Usage: saturn stop <name>", file=sys.stderr)
            return 1
        from .runner import stop_service
        return stop_service(remaining[0])

    if command == 'aider':
        sys.argv = ['aider-saturn'] + remaining
        from .aider_saturn import main as aider_main
        return aider_main()

    from .config import load_service_config
    if load_service_config(command):
        sys.argv = ['saturn-run', command] + remaining
        from .runner import main as runner_main
        return runner_main()

    print(f"Unknown command: {command}", file=sys.stderr)
    print("Run 'saturn --help' for usage", file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main() or 0)
