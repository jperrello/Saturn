import time
import threading
import requests
import socket
from enum import Enum
from zeroconf import ServiceListener, ServiceBrowser, Zeroconf
from typing import Callable, Optional
from collections import defaultdict

 
class ServiceEvent(Enum):
    ADDED = "added"
    REMOVED = "removed"
    UPDATED = "updated"

class ServiceManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance=super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self.services = {}
            self._lock = threading.Lock()
            self._health_cache = {}
            self.zc = Zeroconf()
            self.ai_listener = ZeroconfAIListener(service_manager=self)
            self.browser = ServiceBrowser(self.zc, "_zeroconfai._tcp.local.", self.ai_listener)
            self._event_callbacks = []

    def add_service_to_manager(self, name: str, url: str, info: dict = None):
        with self._lock:
            if name in self.services and self.services[name]["url"] == url:
                print(f"The service: {name} is already registered at {url}")
                return
            self.services[name] = {"url": url, "info": info or {}}
            self._health_cache[url] = (time.time(), True)
        self._notify_event(ServiceEvent.ADDED, name, url)

    def remove_service_from_manager(self, name: str):
        with self._lock:
            if name in self.services:
                url = self.services[name]["url"]
                del self.services[name]
                if url in self._health_cache:
                    del self._health_cache[url]
                self._notify_event(ServiceEvent.REMOVED, name, url)
            else:
                print(f"Tried to remove unknown service: {name}")

    def is_service_available(self, name: str) -> bool:
        with self._lock:
            return name in self.services
    
    def get_service_url(self, name: str) -> Optional[str]:
        with self._lock:
            if name in self.services:
                return self.services[name]["url"]
            return None
        
    def on_service_event(self, callback: Callable[[ServiceEvent, str, str], None]) -> None:
        self._event_callbacks.append(callback)

    def _notify_event(self, event: ServiceEvent, name: str, url: str) -> None:
        for callback in self._event_callbacks:
            try:
                callback(event, name, url)
            except Exception as e:
                print(f"Error in event callback: {e}")        
    
    
    def get_healthy_services(self):
        with self._lock:
            return [(name, info["url"]) for name, info in self.services.items()]
    
    def __iter__(self):
        with self._lock:
            return iter(list(self.services.keys()))
    
    def __len__(self):
        with self._lock:
            return len(self.services)
    
    def __contains__(self, name: str) -> bool:
        with self._lock:
            return name in self.services
    
    def items(self):
        with self._lock:
            return [(name, info["url"]) for name, info in self.services.items()]
    


class ZeroconfAIListener(ServiceListener):
    def __init__(self, service_manager):
        self.service_manager = service_manager

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)

        if info:
            address=socket.inet_ntoa(info.addresses[0])
            port=info.port
            url = f"http://{address}:{port}"
            service_info = {
                "version": info.properties.get(b'version', b'').decode('utf-8'),
                "api": info.properties.get(b'api', b'').decode('utf-8'),
                "priority": info.priority
            }
            self.service_manager.add_service_to_manager(name, url, service_info)
    
    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.add_service(zc, type_, name)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.service_manager.remove_service_from_manager(name)

  
class ZeroconfAIClient:
    def __init__(self, service_manager: ServiceManager, service_name: str = None):
        self.service_manager = service_manager
        self._active_service_name = service_name
        self.chat_history = []
        self.service_available = False

        self.service_manager.on_service_event(self._handle_service_event)

        if service_name:
            self._validate_and_set_service(service_name)
        
    def _validate_and_set_service(self, service_name: str):
        if self.service_manager.is_service_available(service_name):
            self._active_service_name = service_name
            self.service_available = True
        else:
            self.service_available = False
            raise Exception(f"Service {service_name} is not available.")
        
    def _handle_service_event(self, event: ServiceEvent, name: str, url: str):
        if name == self._active_service_name:
            if event == ServiceEvent.REMOVED:
                print(f"Active service {name} at {url} has been removed.")
                self.service_available = False
            elif event == ServiceEvent.ADDED:
                print(f"Active service {name} at {url} has been added.")
                self.service_available = True

    def set_active_service(self, service_name: str):
        self._validate_and_set_service(service_name)

    @property
    def is_connected(self) -> bool:
        return (self._active_service_name is not None and 
                self.service_available and 
                self.service_manager.is_service_available(self._active_service_name))
    
    def get_available_models(self) -> list[str]:
        if not self.is_connected:
            raise RuntimeError(f"No active service {self._active_service_name} is connected.")
        
        url = self.service_manager.get_service_url(self._active_service_name)
        if not url:
            raise RuntimeError(f"Could not get URL for service {self._active_service_name}")
        
        try:
            response = requests.get(f"{url}/v1/models", timeout=5.0)
            response.raise_for_status()
            data = response.json()
            models = data.get('models', [])
            # Handle both list of strings and list of dicts
            if models and isinstance(models[0], dict):
                return [m.get('id', m.get('name', str(m))) for m in models]
            return models
        except requests.RequestException as e:
            print(f"Warning: Could not fetch models from {self._active_service_name}: {e}")
            return []
    
    def chat(self, user_message: str, model: str = None, max_history: int = 10) -> str:
        # Try to reconnect if service was previously unavailable
        if not self.service_available and self._active_service_name:
            url = self.service_manager.get_service_url(self._active_service_name)
            if url and check_health(url, timeout=2.0):
                self.service_available = True
                print(f"Service {self._active_service_name} is available again")

        if not self.is_connected:
            raise RuntimeError(f"No active service {self._active_service_name} is connected.")
        if not self._active_service_name:
            raise RuntimeError("No active service is set. Call set_active_service(name) first.")
        
        url = self.service_manager.get_service_url(self._active_service_name)
        if not url:
            raise RuntimeError(f"Could not get URL for service {self._active_service_name}")
        
        if model is None:
            # Try to get a default model from the service
            available_models = self.get_available_models()
            if not available_models:
                raise RuntimeError(f"No models available from service {self._active_service_name}")
            model = available_models[0]  # Use first available model
            print(f"Using default model: {model}")

        if len(self.chat_history) > max_history * 2:
            self.chat_history = self.chat_history[2:]
        
        current_message = self.chat_history + [{"role": "user", "content": user_message}]
        
        payload = {
            "model": model,
            "messages": current_message,
        }

        try:
            response = requests.post(f"{url}/v1/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            assistant_message = data['choices'][0]['message']['content']
            self.chat_history.append({"role": "user", "content": user_message})
            self.chat_history.append({"role": "assistant", "content": assistant_message})
            return assistant_message
        except requests.RequestException as e:
            self.service_available = False
            raise RuntimeError(f"Error communicating with the AI service {self._active_service_name}: {e}")
        
    def clear_history(self):
        self.chat_history = []

    def get_active_service_info(self) -> Optional[tuple[str, str]]:
        if self._active_service_name:
            url = self.service_manager.get_service_url(self._active_service_name)
            if url:
                return (self._active_service_name, url)
        return None
    

def check_health(url: str, timeout: float = 2.0) -> bool:
    try:
        response = requests.get(f"{url}/v1/health", timeout=timeout)
        return response.status_code == 200
    except:
        return False

def main():
    timeout = 10.0 
    print("Searching for AI services on your network...")

    service_manager = ServiceManager()

    start = time.time()
    print("Waiting for services...") 
    while len(service_manager) == 0 and (time.time() - start) < timeout:
        time.sleep(0.5)
    
    if len(service_manager) == 0:
        raise Exception("No AI Services were found before timeout. Please try again or make sure services are running.")
    
    client = ZeroconfAIClient(service_manager)
    
    try:
        while True:
            services_list = list(service_manager.items())
            for i, (name, url) in enumerate(services_list, 1):
                print(f"{i}. {name} ({url})")
            
            choice = input("\nSelect service (0 to quit): ").strip()
            if choice == "0":
                break

            try:
                choice_idx = int(choice) - 1
                if choice_idx < 0 or choice_idx >= len(services_list):
                    print("Invalid selection. Try again.")
                    continue
                    
                selected_name, selected_url = services_list[choice_idx]
                
                if not service_manager.is_service_available(selected_name):
                    print(f"\nService {selected_name} is no longer available. Please select again.")
                    continue

                if not check_health(selected_url, timeout=5.0):
                    print(f"\nService {selected_name} at {selected_url} is not healthy. Please select again.")
                    service_manager.remove_service_from_manager(selected_name)
                    continue

                client.set_active_service(selected_name)
                print(f"\nConnected to: {selected_name} ({selected_url} with priority {service_manager.services[selected_name]['info'].get('priority', 'N/A')})")
                
                # Fetch and display available models
                try:
                    available_models = client.get_available_models()
                    if available_models:
                        print(f"Available models: {', '.join(available_models)}")
                        print(f"Default model: {available_models[0]}")
                    else:
                        print("Warning: Could not fetch available models")
                except Exception as e:
                    print(f"Warning: Error fetching models: {e}")
                
                print("\nType 'back' to change services, 'clear' to reset chat, or 'quit' to exit\n")
                
                while True:
                    if not client.is_connected:
                        print(f"\nService went offline. Returning to service selection...")
                        break

                    user_input = input("You: ").strip()
                    
                    if user_input.lower() in ['quit', 'exit']:
                        print("Goodbye!")
                        return
                    if user_input.lower() == 'back':
                        print("\nReturning to service selection...")
                        break
                    if user_input.lower() == 'clear':
                        client.clear_history()
                        print("Chat history cleared.\n")
                        continue
                    if not user_input:
                        continue
                    
                    try:
                        response = client.chat(user_input)
                        print(f"Assistant: {response}\n")
                        
                    except RuntimeError as e:
                        print(f"\nError: {e}")
                        
                        if not client.is_connected:
                            if len(service_manager) > 1:
                                print("Other services are available. Returning to selection...")
                                break
                            else:
                                print("No other services available. Exiting...")
                                return
                    
                    except Exception as e:
                        print(f"\n Unexpected error: {e}")
                        print("Returning to service selection...")
                        break
                        
            except (ValueError, IndexError):
                print("Invalid input. Please enter a number.")
                continue
                
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
    finally:
        print("Closing connections and cleaning up...")
        service_manager.browser.cancel()
        service_manager.zc.close()


if __name__ == "__main__":
    main()