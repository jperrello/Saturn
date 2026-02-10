import sys
import os
import subprocess
import argparse
import logging
import requests
from .discovery import discover, select_best_service, SaturnService
from typing import List


def fetch_models(service: SaturnService) -> List[str]:
    if service.is_beacon:
        if not service.ephemeral_key or not service.api_base:
            return []
        url = f"{service.api_base}/models"
        headers = {"Authorization": f"Bearer {service.ephemeral_key}"}
        timeout = 10
    else:
        url = f"{service.endpoint}/v1/models"
        headers = None
        timeout = 5

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.ok:
            data = response.json()
            models = data.get("models", data.get("data", []))
            return [m["id"] if isinstance(m, dict) else m for m in models]
    except Exception:
        pass
    if service.is_beacon:
        return []
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

    g = parser.add_argument_group('Saturn options')
    g.add_argument('--timeout', type=float, default=8.0, help='Discovery timeout in seconds (default: 8.0)')
    g.add_argument('--saturn-needs', help='Required capabilities, comma-separated')
    g.add_argument('--saturn-min-context', type=int, default=0, help='Minimum context window size')
    g.add_argument('--saturn-prefer-free', action=argparse.BooleanOptionalAction, default=True, help='Prefer free services')
    g.add_argument('--saturn-verbose', action='store_true', help='Show discovery details')
    g.add_argument('--select', action='store_true', help='Manually select server and model')
    g.add_argument('--saturn-model', help='Specific model (skips selection)')

    args, aider_args = parser.parse_known_args()
    needs = args.saturn_needs.split(',') if args.saturn_needs else None

    if not args.saturn_verbose:
        logging.getLogger('saturn.discovery').setLevel(logging.WARNING)
        logging.getLogger('discovery').setLevel(logging.WARNING)
        for name in logging.root.manager.loggerDict:
            if 'saturn' in name.lower():
                logging.getLogger(name).setLevel(logging.WARNING)

    print(f"Saturn: Discovering services...")
    services = discover(timeout=args.timeout)

    if not services:
        print("Saturn: No services found on the network.", file=sys.stderr)
        print("Saturn: Ensure a Saturn server is running (e.g., saturn beacon, saturn openrouter).", file=sys.stderr)
        sys.exit(1)

    if args.select:
        print(f"Saturn: Found {len(services)} service(s):")
        for i, svc in enumerate(services, 1):
            if svc.is_cloud:
                print(f"  [{i}] {svc.name} (cloud -> {svc.api_base})")
                print(f"      deployment: {svc.deployment} | api_type: {svc.api_type} | priority: {svc.priority}")
            else:
                models_preview = ', '.join(svc.models[:3]) + ('...' if len(svc.models) > 3 else '')
                print(f"  [{i}] {svc.name} at {svc.effective_endpoint}")
                print(f"      deployment: {svc.deployment} | api_type: {svc.api_type}")
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
            prefer_free=args.saturn_prefer_free
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
        models = fetch_models(service)
        if not models:
            print(f"Saturn: No models available from {service.name}.", file=sys.stderr)
            sys.exit(1)

        if args.select:
            selected_model = select_model(models, service.name)
        else:
            selected_model = models[0]

    if service.is_cloud:
        if not service.api_base:
            print(f"Saturn: Cloud service {service.name} missing api_base", file=sys.stderr)
            sys.exit(1)
        base_url = service.api_base
        print(f"Saturn: Using {service.name} (cloud) -> {service.api_base}")
        print(f"Saturn: Model: {selected_model}")
        api_key = service.ephemeral_key or 'saturn'
    else:
        base_url = service.effective_endpoint
        print(f"Saturn: Using {service.name} (network) at {base_url}")
        print(f"Saturn: Model: {selected_model}")
        api_key = 'saturn'

    env = os.environ.copy()
    env['OPENAI_BASE_URL'] = base_url
    env['OPENAI_API_KEY'] = api_key

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
