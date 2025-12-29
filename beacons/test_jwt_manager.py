from jwt_manager import JWTManager
import time
import os
from pathlib import Path


def load_env():
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value


def test_jwt_manager():
    load_env()
    print("Testing JWTManager...")

    manager = JWTManager(expires_delta=600, rotation_interval=300)

    print("\n1. Initial state - needs_rotation should be True")
    print(f"   needs_rotation: {manager.needs_rotation()}")
    print(f"   current_token: {manager.get_current_token()}")

    print("\n2. Generating first token (all models, no spending limit)...")
    token = manager.generate_token()
    print(f"   Token generated: {token[:50]}...")
    print(f"   Token length: {len(token)} characters")

    print("\n3. After generation - needs_rotation should be False")
    print(f"   needs_rotation: {manager.needs_rotation()}")
    print(f"   current_token exists: {manager.get_current_token() is not None}")

    print("\n4. Token info:")
    info = manager.get_token_info()
    for key, value in info.items():
        print(f"   {key}: {value}")

    print("\n5. Testing token with DeepInfra API...")
    import requests
    response = requests.post(
        "https://api.deepinfra.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "model": "meta-llama/Meta-Llama-3.1-8B-Instruct",
            "messages": [{"role": "user", "content": "Say 'test passed' and nothing else"}]
        }
    )
    if response.status_code == 200:
        print(f"   API call successful: {response.json()['choices'][0]['message']['content']}")
    else:
        print(f"   API call failed: {response.status_code} - {response.text}")

    print("\n6. Simulating time passage (testing rotation detection)...")
    print(f"   Waiting 2 seconds...")
    time.sleep(2)
    print(f"   needs_rotation after 2s: {manager.needs_rotation()}")

    print("\n[SUCCESS] All tests passed!")


if __name__ == "__main__":
    test_jwt_manager()
