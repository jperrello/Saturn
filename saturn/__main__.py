import sys


def main():
    if len(sys.argv) < 2:
        print("Saturn: Zero-configuration AI service discovery")
        print()
        print("Usage: saturn <command> [options]")
        print()
        print("Commands:")
        print("  discover      Discover Saturn services on the network")
        print("  endpoint      Output best service endpoint URL (for scripts)")
        print("  config        Manage service configurations")
        print("  run           Run a configured service")
        print("  stop          Stop a running service")
        print()
        print("Shortcuts (alias for 'saturn run <name>'):")
        from .config import list_service_configs
        for name, cfg, _ in list_service_configs():
            beacon = " [beacon]" if cfg.beacon.enabled else ""
            print(f"  {name:<16}{cfg.api_type} @ {cfg.upstream.base_url or '(self-contained)'}{beacon}")
        print()
        print("Tools:")
        print("  aider         Launch Aider with auto-discovered Saturn service")
        print()
        print("Examples:")
        print("  saturn discover")
        print("  saturn config list")
        print("  saturn run myservice")
        return 0

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

    # treat any other command as a service name shortcut
    from .config import load_service_config
    if load_service_config(command):
        sys.argv = ['saturn-run', command] + remaining
        from .runner import main as runner_main
        return runner_main()

    print(f"Unknown command: {command}", file=sys.stderr)
    print("Run 'saturn' for usage", file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main() or 0)
