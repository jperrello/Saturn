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
        print("  deepinfra     DeepInfra beacon - broadcasts JWT for direct calls")
        print("  orbeacon      OpenRouter beacon - broadcasts keys for direct calls")
        print("  beacon-proxy  HTTP proxy server - guests connect here, traffic proxied")
        print("  openrouter    Start OpenRouter server with mDNS registration")
        print("  ollama        Start Ollama server with mDNS registration")
        print("  fallback      Start mock fallback server for testing")
        print("  aider         Launch Aider with auto-discovered Saturn service")
        print()
        print("Examples:")
        print("  saturn discover")
        print("  saturn deepinfra --priority 10")
        print("  saturn orbeacon --priority 10")
        print("  saturn beacon-proxy --priority 10")
        print("  saturn openrouter --priority 50")
        print("  saturn aider --select")
        return 0

    command = sys.argv[1]
    remaining = sys.argv[2:]

    if command in ('discover', 'endpoint'):
        sys.argv = ['saturn', command] + remaining
        from .discovery import main as discovery_main
        return discovery_main()

    elif command == 'deepinfra':
        sys.argv = ['saturn-deepinfra'] + remaining
        from .deepinfra_beacon import main as deepinfra_main
        return deepinfra_main()

    elif command == 'orbeacon':
        sys.argv = ['saturn-orbeacon'] + remaining
        from .openrouter_beacon import main as orbeacon_main
        return orbeacon_main()

    elif command == 'beacon-proxy':
        sys.argv = ['saturn-beacon-proxy'] + remaining
        from .beacon_proxy import main as beacon_proxy_main
        return beacon_proxy_main()

    elif command == 'openrouter':
        sys.argv = ['saturn-openrouter'] + remaining
        from .openrouter_server import main as openrouter_main
        return openrouter_main()

    elif command == 'ollama':
        sys.argv = ['saturn-ollama'] + remaining
        from .ollama_server import main as ollama_main
        return ollama_main()

    elif command == 'fallback':
        sys.argv = ['saturn-fallback'] + remaining
        from .fallback_server import main as fallback_main
        return fallback_main()

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
