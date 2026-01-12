from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
import socket
import time
import requests
import threading
import os
import base64
import mimetypes
import hashlib
from pathlib import Path
from typing import Optional
import tiktoken
from PIL import Image

DEEPINFRA_API_URL = "https://api.deepinfra.com/v1/chat/completions"

class TokenTracker:
    def __init__(self, warning_cost_cents=25):
        self.warning_cost_cents = warning_cost_cents
        self.encoding = tiktoken.get_encoding("o200k_base")
        self.lock = threading.Lock()
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.warned = False

    def estimate_text_tokens(self, text):
        return len(self.encoding.encode(text))

    def estimate_image_tokens(self, width, height):
        tiles = ((width + 511) // 512) * ((height + 511) // 512)
        return 85 + 170 * tiles

    def estimate_cost(self, tokens, avg_cost_per_1m=3.0):
        return (tokens / 1_000_000) * avg_cost_per_1m

    def update_usage(self, input_tokens, output_tokens):
        with self.lock:
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens

            avg_cost = 3.0
            input_cost = (input_tokens / 1_000_000) * avg_cost
            output_cost = (output_tokens / 1_000_000) * avg_cost
            self.total_cost += input_cost + output_cost

            if self.total_cost >= self.warning_cost_cents / 100 and not self.warned:
                self.warned = True
                return True
        return False

    def get_summary(self):
        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "cost_usd": self.total_cost,
            "cost_cents": self.total_cost * 100
        }


class FileContextManager:
    def __init__(self, token_tracker):
        self.files = {}
        self.token_tracker = token_tracker

    def guess_file_type(self, filepath):
        mime_type, _ = mimetypes.guess_type(filepath)

        if not mime_type:
            mime_type = "application/octet-stream"

        if mime_type.startswith('text/'):
            return 'text', mime_type

        text_mimes = [
            'application/json',
            'application/javascript',
            'application/x-python',
            'application/xml',
            'application/x-sh'
        ]
        if mime_type in text_mimes:
            return 'text', mime_type

        if any(filepath.endswith(ext) for ext in ['.py', '.js', '.ts', '.java', '.cpp', '.c',
                                                    '.h', '.rs', '.go', '.rb', '.php', '.swift',
                                                    '.kt', '.scala', '.sh', '.bash', '.md', '.txt',
                                                    '.json', '.xml', '.yaml', '.yml', '.toml', '.ini',
                                                    '.conf', '.log', '.sql', '.html', '.css', '.scss', '.lua']):
            return 'text', mime_type

        image_types = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp']
        if mime_type in image_types:
            return 'image', mime_type

        if mime_type == 'application/pdf':
            return 'pdf', mime_type

        return 'binary', mime_type

    def upload_file(self, filepath):
        if not os.path.exists(filepath):
            return False, f"File not found: {filepath}"

        filename = os.path.basename(filepath)

        if filename in self.files:
            return False, f"File '{filename}' already uploaded. Use /remove first to replace."

        file_type, mime_type = self.guess_file_type(filepath)

        if file_type == 'text':
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                token_count = self.token_tracker.estimate_text_tokens(content)
                cost_estimate = self.token_tracker.estimate_cost(token_count)

                self.files[filename] = {
                    'type': 'text',
                    'content': content,
                    'mime_type': mime_type,
                    'tokens': token_count,
                    'cost_estimate': cost_estimate
                }

                return True, f"Uploaded {filename} (text, ~{token_count} tokens, ~${cost_estimate:.4f})"
            except Exception as e:
                return False, f"Error reading text file: {e}"

        elif file_type == 'image':
            try:
                with Image.open(filepath) as img:
                    width, height = img.size

                with open(filepath, 'rb') as f:
                    encoded = base64.b64encode(f.read()).decode('utf-8')

                data_uri = f"data:{mime_type};base64,{encoded}"
                token_count = self.token_tracker.estimate_image_tokens(width, height)
                cost_estimate = self.token_tracker.estimate_cost(token_count)

                self.files[filename] = {
                    'type': 'image',
                    'content': data_uri,
                    'mime_type': mime_type,
                    'tokens': token_count,
                    'cost_estimate': cost_estimate,
                    'dimensions': (width, height)
                }

                size_warning = ""
                if width > 2048 or height > 2048:
                    size_warning = f" Warning: Large image ({width}x{height}), consider resizing"

                return True, f"Uploaded {filename} (image, ~{token_count} tokens, ~${cost_estimate:.4f}){size_warning}"
            except Exception as e:
                return False, f"Error reading image file: {e}"

        elif file_type == 'pdf':
            return False, "PDF support coming soon (PDFs are expensive - each page becomes an image)"

        else:
            return False, f"Unsupported file type: {mime_type}"

    def remove_file(self, filename):
        if filename in self.files:
            del self.files[filename]
            return True, f"Removed {filename}"
        return False, f"File not found: {filename}"

    def clear_all(self):
        count = len(self.files)
        self.files.clear()
        return f"Cleared {count} file(s)"

    def list_files(self):
        if not self.files:
            return "No files uploaded"

        lines = [f"Context files ({len(self.files)} total):"]
        total_tokens = 0
        total_cost = 0

        for i, (filename, info) in enumerate(self.files.items(), 1):
            total_tokens += info['tokens']
            total_cost += info['cost_estimate']

            if info['type'] == 'text':
                lines.append(f"  {i}. {filename} (text, ~{info['tokens']} tokens)")
            elif info['type'] == 'image':
                w, h = info['dimensions']
                lines.append(f"  {i}. {filename} (image, {w}x{h}, ~{info['tokens']} tokens)")

        lines.append(f"\nTotal: ~{total_tokens} tokens, ~${total_cost:.4f}")
        return "\n".join(lines)

    def build_context_message(self):
        if not self.files:
            return None

        content_blocks = []

        text_files = []
        for filename, info in self.files.items():
            if info['type'] == 'text':
                text_files.append(f"# {filename}\n{info['content']}")

        if text_files:
            combined_text = "\n\n---\n\n".join(text_files)
            content_blocks.append({
                "type": "text",
                "text": f"Here are the uploaded files for context:\n\n{combined_text}"
            })

        for filename, info in self.files.items():
            if info['type'] == 'image':
                content_blocks.append({
                    "type": "image_url",
                    "image_url": {"url": info['content']}
                })

        if content_blocks:
            return {"role": "user", "content": content_blocks}
        return None


class SimpleListener(ServiceListener):
    def __init__(self, on_service_change=None):
        self.services = {}
        self.lock = threading.Lock()
        self.service_found = threading.Event()
        self.on_service_change = on_service_change

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if not info:
            return

        with self.lock:
            address = socket.inet_ntoa(info.addresses[0])
            port = info.port
            url = f"http://{address}:{port}"
            priority = int(info.properties.get(b'priority', b'50').decode('utf-8'))

            ephemeral_key = None
            ephemeral_key_bytes = info.properties.get(b'ephemeral_key')
            if ephemeral_key_bytes:
                ephemeral_key = ephemeral_key_bytes.decode('utf-8')

            clean_name = name.replace('._saturn._tcp.local.', '')

            is_new = clean_name not in self.services
            old_key = None
            if not is_new:
                old_key = self.services[clean_name].get('ephemeral_key')

            self.services[clean_name] = {
                'url': url,
                'priority': priority,
                'ephemeral_key': ephemeral_key
            }
            self.service_found.set()

            if ephemeral_key:
                key_hash = hashlib.sha256(ephemeral_key.encode()).hexdigest()[:12]
                if is_new:
                    print(f"  Discovered beacon: {clean_name}")
                    print(f"    JWT fingerprint: {key_hash}")
                elif old_key and old_key != ephemeral_key:
                    print(f"  Key rotated for {clean_name}")
                    print(f"    New JWT fingerprint: {key_hash}")
            elif is_new:
                if self.on_service_change:
                    self.on_service_change('added', clean_name, url, priority)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        clean_name = name.replace('._saturn._tcp.local.', '')

        with self.lock:
            if clean_name in self.services:
                service_info = self.services[clean_name]
                del self.services[clean_name]

                if self.on_service_change:
                    self.on_service_change('removed', clean_name, service_info['url'], service_info['priority'])

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.add_service(zc, type_, name)

    def get_best_service(self):
        with self.lock:
            if not self.services:
                return None, None, None
            best = min(self.services.items(), key=lambda x: x[1]['priority'])
            return best[0], best[1]['url'], best[1].get('ephemeral_key')

    def get_all_services(self):
        with self.lock:
            return sorted(self.services.items(), key=lambda x: x[1]['priority'])


def call_deepinfra_api(ephemeral_key: str, model: str, messages: list) -> Optional[dict]:
    headers = {
        "Authorization": f"Bearer {ephemeral_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": messages
    }

    try:
        response = requests.post(DEEPINFRA_API_URL, headers=headers, json=payload, timeout=120)
        if response.ok:
            return response.json()
        else:
            print(f"DeepInfra API error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"DeepInfra API call failed: {e}")
        return None


def main():
    service_notifications = []
    notification_lock = threading.Lock()

    def handle_service_change(action, name, url, priority):
        with notification_lock:
            if action == 'added':
                service_notifications.append(f"\n  New server discovered: {name} at {url} (priority: {priority})")
            elif action == 'removed':
                service_notifications.append(f"\n  Server removed: {name} (was at {url})")

    zc = Zeroconf()
    listener = SimpleListener(on_service_change=handle_service_change)
    browser = ServiceBrowser(zc, "_saturn._tcp.local.", listener)

    print("Searching for Saturn services and beacons...")
    time.sleep(1.5)
    if not listener.service_found.wait(timeout=3.0):
        print("No Saturn services found.")
        browser.cancel()
        zc.close()
        return

    current_server_name, current_service_url, current_ephemeral_key = listener.get_best_service()
    if not current_service_url:
        print("No Saturn services found.")
        browser.cancel()
        zc.close()
        return

    using_beacon = current_ephemeral_key is not None
    current_model = None

    if using_beacon:
        key_hash = hashlib.sha256(current_ephemeral_key.encode()).hexdigest()[:12]
        print(f"Connected to BEACON: {current_server_name}")
        print(f"  URL: {current_service_url}")
        print(f"  JWT fingerprint: {key_hash}")
        print(f"  (Calling DeepInfra API directly)")
        current_model = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    else:
        print(f"Connected to server: {current_server_name} at {current_service_url}")
        print("  (Discovery continues in background - new servers will be detected automatically)")

        try:
            models_response = requests.get(f"{current_service_url}/v1/models", timeout=5)
            if models_response.ok:
                available_models = [model['id'] for model in models_response.json().get('models', [])]
                if available_models:
                    current_model = available_models[0]
                    print(f"Using model: {current_model}")
                else:
                    print("No models available from this server")
                    browser.cancel()
                    zc.close()
                    return
            else:
                print(f"Failed to fetch models from server")
                browser.cancel()
                zc.close()
                return
        except Exception as e:
            print(f"Error fetching models: {e}")
            browser.cancel()
            zc.close()
            return

    token_tracker = TokenTracker(warning_cost_cents=25)
    file_manager = FileContextManager(token_tracker)

    chat_history = []
    context_injected = False

    print("\n" + "="*60)
    print("Saturn File Upload Client")
    print("="*60)
    print("\nCommands:")
    print("  /upload <filepath>  - Upload a file for context")
    print("  /list              - List uploaded files")
    print("  /remove <filename> - Remove a specific file")
    print("  /clear-files       - Remove all files")
    print("  /clear             - Clear chat history")
    print("  /info              - Show token usage info")
    print("  /servers           - List all available servers")
    print("  /change-server     - Change to a different server")
    print("  /models            - List available models on current server")
    print("  /change-model      - Change to a different model")
    print("  quit               - Exit")
    print("="*60 + "\n")

    while True:
        with notification_lock:
            if service_notifications:
                for notification in service_notifications:
                    print(notification)
                service_notifications.clear()
                print()

        current_server_name, current_service_url, current_ephemeral_key = listener.get_best_service()
        if not current_service_url:
            print("\n  All servers offline! Waiting for services...")
            time.sleep(2)
            continue

        using_beacon = current_ephemeral_key is not None

        user_input = input("You: ").strip()

        if not user_input:
            continue

        if user_input.lower() == "quit":
            break

        if user_input.startswith("/upload "):
            filepath = user_input[8:].strip()
            success, message = file_manager.upload_file(filepath)
            print(message)
            context_injected = False
            continue

        elif user_input == "/list":
            print(file_manager.list_files())
            continue

        elif user_input.startswith("/remove "):
            filename = user_input[8:].strip()
            success, message = file_manager.remove_file(filename)
            print(message)
            if success:
                context_injected = False
            continue

        elif user_input == "/clear-files":
            message = file_manager.clear_all()
            print(message)
            context_injected = False
            continue

        elif user_input == "/clear":
            chat_history = []
            context_injected = False
            print("Chat history cleared.")
            continue

        elif user_input == "/info":
            summary = token_tracker.get_summary()
            print(f"\nToken Usage:")
            print(f"  Input tokens:  {summary['input_tokens']}")
            print(f"  Output tokens: {summary['output_tokens']}")
            print(f"  Total cost:    ${summary['cost_usd']:.4f} ({summary['cost_cents']:.2f} cents)")
            print(f"  Warning at:    ${token_tracker.warning_cost_cents/100:.2f}")
            continue

        elif user_input == "/servers":
            all_services = listener.get_all_services()
            if not all_services:
                print("No servers discovered")
            else:
                print(f"\nAvailable servers (current: {current_server_name}):")
                for name, info in all_services:
                    marker = " <- current" if name == current_server_name else ""
                    beacon_marker = " [BEACON]" if info.get('ephemeral_key') else ""
                    print(f"  - {name} (priority: {info['priority']}, url: {info['url']}){beacon_marker}{marker}")
            continue

        elif user_input == "/change-server":
            all_services = listener.get_all_services()
            if len(all_services) <= 1:
                print("Only one server available")
                continue

            print("\nAvailable servers:")
            for i, (name, info) in enumerate(all_services, 1):
                marker = " <- current" if name == current_server_name else ""
                beacon_marker = " [BEACON]" if info.get('ephemeral_key') else ""
                print(f"  {i}. {name} (priority: {info['priority']}){beacon_marker}{marker}")

            try:
                choice = input("\nEnter server name or number: ").strip()

                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(all_services):
                        new_server_name, new_server_info = all_services[idx]
                    else:
                        print("Invalid number")
                        continue
                except ValueError:
                    matching = [s for s in all_services if s[0] == choice]
                    if matching:
                        new_server_name, new_server_info = matching[0]
                    else:
                        print(f"Server '{choice}' not found")
                        continue

                current_server_name = new_server_name
                current_service_url = new_server_info['url']
                current_ephemeral_key = new_server_info.get('ephemeral_key')
                using_beacon = current_ephemeral_key is not None

                if using_beacon:
                    key_hash = hashlib.sha256(current_ephemeral_key.encode()).hexdigest()[:12]
                    print(f"Switched to BEACON: {current_server_name}")
                    print(f"  JWT fingerprint: {key_hash}")
                    current_model = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
                    chat_history = []
                    context_injected = False
                else:
                    try:
                        models_response = requests.get(f"{current_service_url}/v1/models", timeout=5)
                        if models_response.ok:
                            available_models = [model['id'] for model in models_response.json().get('models', [])]
                            if available_models:
                                current_model = available_models[0]
                                print(f"Switched to server: {current_server_name}")
                                print(f"Using model: {current_model}")
                                chat_history = []
                                context_injected = False
                            else:
                                print("No models available from this server")
                        else:
                            print(f"Failed to fetch models from server")
                    except Exception as e:
                        print(f"Error fetching models: {e}")
            except KeyboardInterrupt:
                print("\nCancelled")
            continue

        elif user_input == "/models":
            if using_beacon:
                print(f"\nBeacon mode - using default model: {current_model}")
                continue
            try:
                models_response = requests.get(f"{current_service_url}/v1/models", timeout=5)
                if models_response.ok:
                    available_models = [model['id'] for model in models_response.json().get('models', [])]
                    if available_models:
                        print(f"\nAvailable models on {current_server_name} (current: {current_model}):")
                        for i, model in enumerate(available_models, 1):
                            marker = " <- current" if model == current_model else ""
                            print(f"  {i}. {model}{marker}")
                    else:
                        print("No models available")
                else:
                    print("Failed to fetch models")
            except Exception as e:
                print(f"Error: {e}")
            continue

        elif user_input == "/change-model":
            if using_beacon:
                print("Beacon mode - model is fixed to DeepInfra default")
                continue
            try:
                models_response = requests.get(f"{current_service_url}/v1/models", timeout=5)
                if models_response.ok:
                    available_models = [model['id'] for model in models_response.json().get('models', [])]
                    if not available_models:
                        print("No models available")
                        continue

                    print("\nAvailable models:")
                    for i, model in enumerate(available_models, 1):
                        marker = " <- current" if model == current_model else ""
                        print(f"  {i}. {model}{marker}")

                    choice = input("\nEnter model name or number: ").strip()

                    try:
                        idx = int(choice) - 1
                        if 0 <= idx < len(available_models):
                            current_model = available_models[idx]
                            print(f"Switched to model: {current_model}")
                        else:
                            print("Invalid number")
                    except ValueError:
                        if choice in available_models:
                            current_model = choice
                            print(f"Switched to model: {current_model}")
                        else:
                            print(f"Model '{choice}' not found")
                else:
                    print("Failed to fetch models")
            except KeyboardInterrupt:
                print("\nCancelled")
            except Exception as e:
                print(f"Error: {e}")
            continue

        elif user_input.startswith("/"):
            print(f"Unknown command: {user_input}")
            continue

        context_msg = file_manager.build_context_message()
        if context_msg and not context_injected:
            chat_history.insert(0, context_msg)
            chat_history.insert(1, {"role": "assistant", "content": "I can see your uploaded files. What would you like to know?"})
            context_injected = True

        current_message = chat_history + [{"role": "user", "content": user_input}]

        if using_beacon:
            key_hash = hashlib.sha256(current_ephemeral_key.encode()).hexdigest()[:12]
            print(f"  (Using JWT: {key_hash})")

            data = call_deepinfra_api(
                ephemeral_key=current_ephemeral_key,
                model=current_model,
                messages=current_message
            )

            if data:
                assistant_message = data['choices'][0]['message']['content']
                print(f"AI: {assistant_message}")

                usage = data.get('usage', {})
                if usage:
                    input_tokens = usage.get('prompt_tokens', 0)
                    output_tokens = usage.get('completion_tokens', 0)

                    if token_tracker.update_usage(input_tokens, output_tokens):
                        print(f"\n  WARNING: Cost exceeded ${token_tracker.warning_cost_cents/100:.2f}!")
                        summary = token_tracker.get_summary()
                        print(f"Current cost: ${summary['cost_usd']:.4f}")
                        print("Continuing anyway... (use /info to check usage)\n")

                chat_history.append({"role": "user", "content": user_input})
                chat_history.append({"role": "assistant", "content": assistant_message})
            else:
                print("Error: Failed to get response from DeepInfra API")
        else:
            payload = {
                "model": current_model,
                "messages": current_message
            }

            try:
                response = requests.post(
                    f"{current_service_url}/v1/chat/completions",
                    json=payload,
                    timeout=120
                )

                if response.ok:
                    data = response.json()
                    assistant_message = data['choices'][0]['message']['content']
                    print(f"AI: {assistant_message}")

                    usage = data.get('usage', {})
                    if usage:
                        input_tokens = usage.get('prompt_tokens', 0)
                        output_tokens = usage.get('completion_tokens', 0)

                        if token_tracker.update_usage(input_tokens, output_tokens):
                            print(f"\n  WARNING: Cost exceeded ${token_tracker.warning_cost_cents/100:.2f}!")
                            summary = token_tracker.get_summary()
                            print(f"Current cost: ${summary['cost_usd']:.4f}")
                            print("Continuing anyway... (use /info to check usage)\n")

                    chat_history.append({"role": "user", "content": user_input})
                    chat_history.append({"role": "assistant", "content": assistant_message})
                else:
                    print(f"Error: {response.status_code} - {response.text}")

            except requests.exceptions.Timeout:
                print("Request timed out. Try again.")
            except Exception as e:
                print(f"Error: {e}")

    browser.cancel()
    zc.close()

    summary = token_tracker.get_summary()
    print(f"\nSession complete!")
    print(f"Total tokens: {summary['input_tokens'] + summary['output_tokens']}")
    print(f"Total cost: ${summary['cost_usd']:.4f}")


if __name__ == "__main__":
    main()
