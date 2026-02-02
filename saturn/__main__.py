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
        print("Services (alias for 'saturn run <name>'):")
        print("  openrouter    OpenRouter proxy server")
        print("  ollama        Ollama proxy server")
        print("  deepinfra     DeepInfra beacon (broadcasts JWT)")
        print("  orbeacon      OpenRouter beacon (broadcasts ephemeral keys)")
        print("  beacon-proxy  DeepInfra HTTP proxy with JWT rotation")
        print("  fallback      Mock fallback server for testing")
        print()
        print("Tools:")
        print("  aider         Launch Aider with auto-discovered Saturn service")
        print()
        print("Examples:")
        print("  saturn discover")
        print("  saturn config list")
        print("  saturn config edit myservice")
        print("  saturn run myservice")
        print("  saturn run -l")
        return 0

    command = sys.argv[1]
    remaining = sys.argv[2:]

    if command in ('discover', 'endpoint'):
        sys.argv = ['saturn', command] + remaining
        from .discovery import main as discovery_main
        return discovery_main()

    elif command == 'config':
        sys.argv = ['saturn-config'] + remaining
        from .config import main as config_main
        return config_main()

    elif command == 'run':
        sys.argv = ['saturn-run'] + remaining
        from .runner import main as runner_main
        return runner_main()

    elif command == 'stop':
        if not remaining:
            print("Usage: saturn stop <name>", file=sys.stderr)
            return 1
        from .runner import stop_service
        return stop_service(remaining[0])

    elif command == 'deepinfra':
        sys.argv = ['saturn-run', 'deepinfra'] + remaining
        from .runner import main as runner_main
        return runner_main()

    elif command == 'orbeacon':
        sys.argv = ['saturn-run', 'orbeacon'] + remaining
        from .runner import main as runner_main
        return runner_main()

    elif command == 'beacon-proxy':
        sys.argv = ['saturn-run', 'beacon-proxy'] + remaining
        from .runner import main as runner_main
        return runner_main()

    elif command == 'openrouter':
        sys.argv = ['saturn-run', 'openrouter'] + remaining
        from .runner import main as runner_main
        return runner_main()

    elif command == 'ollama':
        sys.argv = ['saturn-run', 'ollama'] + remaining
        from .runner import main as runner_main
        return runner_main()

    elif command == 'fallback':
        sys.argv = ['saturn-run', 'fallback'] + remaining
        from .runner import main as runner_main
        return runner_main()

    elif command == 'aider':
        sys.argv = ['aider-saturn'] + remaining
        from .aider_saturn import main as aider_main
        return aider_main()

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print("Run 'saturn' for usage", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main() or 0)
