import sys
import os
import subprocess
import argparse
import logging
import requests
from .discovery import discover_services, select_best_service, SaturnService
from typing import List


def fetch_service_models(service: SaturnService) -> List[str]:
    try:
        response = requests.get(f"{service.endpoint}/v1/models", timeout=5)
        if response.ok:
            data = response.json()
            models = data.get("models", data.get("data", []))
            return [m["id"] if isinstance(m, dict) else m for m in models]
    except Exception:
        pass
    return service.models


def select_model(models: List[str], service_name: str) -> str:
    if not models:
        return None

    print(f"\nSaturn: Available models from {service_name}:")
    display_models = models[:10]
    for i, model in enumerate(display_models, 1):
        print(f"  [{i}] {model}")
    if len(models) > 10:
        print(f"  ... and {len(models) - 10} more")

    while True:
        try:
            choice = input(f"\nSelect model [1-{len(display_models)}] (Enter for first): ").strip()
            if not choice:
                return models[0]
            idx = int(choice) - 1
            if 0 <= idx < len(display_models):
                return display_models[idx]
            print(f"Please enter a number between 1 and {len(display_models)}")
        except ValueError:
            print("Please enter a valid number")
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog='aider-saturn',
        description='Launch Aider with zero-configuration Saturn service discovery',
        epilog='All unrecognized arguments are passed directly to Aider.'
    )

    saturn_group = parser.add_argument_group('Saturn options')
    saturn_group.add_argument(
        '--timeout', type=float, default=8.0,
        help='Service discovery timeout in seconds (default: 8.0)'
    )
    saturn_group.add_argument(
        '--saturn-needs', type=str, default=None,
        help='Required capabilities, comma-separated (e.g., "chat,code,vision")'
    )
    saturn_group.add_argument(
        '--saturn-min-context', type=int, default=0,
        help='Minimum context window size required'
    )
    saturn_group.add_argument(
        '--saturn-prefer-free', action='store_true', default=True,
        help='Prefer free services over paid (default: true)'
    )
    saturn_group.add_argument(
        '--saturn-no-prefer-free', action='store_true',
        help='Do not prefer free services'
    )
    saturn_group.add_argument(
        '--saturn-verbose', action='store_true',
        help='Show Saturn discovery details'
    )
    saturn_group.add_argument(
        '--select', action='store_true',
        help='Manually select which server and model to use'
    )
    saturn_group.add_argument(
        '--saturn-model', type=str, default=None,
        help='Specific model to use (skips model selection)'
    )

    args, aider_args = parser.parse_known_args()

    prefer_free = args.saturn_prefer_free and not args.saturn_no_prefer_free
    needs = args.saturn_needs.split(',') if args.saturn_needs else None

    if not args.saturn_verbose:
        logging.getLogger('saturn.discovery').setLevel(logging.WARNING)
        logging.getLogger('discovery').setLevel(logging.WARNING)
        for name in logging.root.manager.loggerDict:
            if 'saturn' in name.lower():
                logging.getLogger(name).setLevel(logging.WARNING)

    print(f"Saturn: Discovering services...")
    services = discover_services(timeout=args.timeout)

    if not services:
        print("Saturn: No services found on the network.", file=sys.stderr)
        print("Saturn: Ensure a Saturn server is running (e.g., saturn beacon, saturn openrouter).", file=sys.stderr)
        sys.exit(1)

    if args.select:
        print(f"Saturn: Found {len(services)} service(s):")
        for i, svc in enumerate(services, 1):
            models_preview = ', '.join(svc.models[:3]) + ('...' if len(svc.models) > 3 else '')
            print(f"  [{i}] {svc.name} at {svc.endpoint}")
            print(f"      models: {models_preview or 'none'}")
            print(f"      context: {svc.context} | cost: {svc.cost} | priority: {svc.priority}")

        while True:
            try:
                choice = input(f"\nSelect service [1-{len(services)}]: ").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(services):
                    service = services[idx]
                    break
                print(f"Please enter a number between 1 and {len(services)}")
            except ValueError:
                print("Please enter a valid number")
            except (EOFError, KeyboardInterrupt):
                print("\nCancelled.")
                sys.exit(1)
    else:
        service = select_best_service(
            services,
            needs=needs,
            min_context=args.saturn_min_context,
            prefer_free=prefer_free
        )

        if not service:
            criteria = []
            if needs:
                criteria.append(f"capabilities: {args.saturn_needs}")
            if args.saturn_min_context:
                criteria.append(f"min context: {args.saturn_min_context}")
            print(f"Saturn: No services match criteria ({', '.join(criteria)}).", file=sys.stderr)
            print(f"Saturn: {len(services)} service(s) available but none match requirements.", file=sys.stderr)
            sys.exit(1)

    if args.saturn_model:
        selected_model = args.saturn_model
    else:
        models = fetch_service_models(service)
        if not models:
            print(f"Saturn: No models available from {service.name}.", file=sys.stderr)
            sys.exit(1)

        if args.select:
            selected_model = select_model(models, service.name)
        else:
            selected_model = models[0]

    print(f"Saturn: Using {service.name} at {service.endpoint}")
    print(f"Saturn: Model: {selected_model}")

    # inject env vars so aider talks to saturn instead of openai directly
    # api key can be anything, saturn servers don't validate it (auth is network-level)
    env = os.environ.copy()
    env['OPENAI_BASE_URL'] = f"{service.endpoint}/v1"
    env['OPENAI_API_KEY'] = 'saturn'

    cmd = ['aider', '--model', f'openai/{selected_model}'] + aider_args

    try:
        result = subprocess.run(cmd, env=env)
        sys.exit(result.returncode)
    except FileNotFoundError:
        print("Saturn: 'aider' command not found.", file=sys.stderr)
        print("Saturn: Install Aider with: pip install aider-chat", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == '__main__':
    main()
