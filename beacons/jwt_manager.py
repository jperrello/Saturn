import os
import time
import threading
import requests
from typing import Optional
from datetime import datetime, timedelta


class JWTManager:
    def __init__(self, api_key: Optional[str] = None,
                 expires_delta: int = 600,
                 rotation_interval: int = 300):
        self.api_key = api_key or os.getenv('DEEPINFRA_API_KEY')
        if not self.api_key:
            raise ValueError("DEEPINFRA_API_KEY not found in environment or constructor")

        self.expires_delta = expires_delta
        self.rotation_interval = rotation_interval
        self.api_endpoint = "https://api.deepinfra.com/v1/scoped-jwt"

        self._lock = threading.Lock()
        self._current_token: Optional[str] = None
        self._expires_at: Optional[float] = None
        self._last_rotation: Optional[float] = None

    def generate_token(self, models: Optional[list] = None, spending_limit: Optional[float] = None) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "api_key_name": "auto",
            "expires_delta": self.expires_delta
        }

        if models is not None:
            payload["models"] = models
            if spending_limit is not None:
                payload["spending_limit"] = spending_limit

        response = requests.post(self.api_endpoint, headers=headers, json=payload)
        response.raise_for_status()

        token = response.json()["token"]

        with self._lock:
            self._current_token = token
            self._expires_at = time.time() + self.expires_delta
            self._last_rotation = time.time()

        return token

    def get_current_token(self) -> Optional[str]:
        with self._lock:
            return self._current_token

    def needs_rotation(self) -> bool:
        with self._lock:
            if self._last_rotation is None:
                return True

            time_since_rotation = time.time() - self._last_rotation
            return time_since_rotation >= self.rotation_interval

    def get_token_info(self) -> dict:
        with self._lock:
            if self._current_token is None:
                return {
                    "has_token": False,
                    "expires_at": None,
                    "time_until_expiry": None,
                    "time_until_rotation": None
                }

            now = time.time()
            time_until_expiry = self._expires_at - now if self._expires_at else None
            time_until_rotation = self.rotation_interval - (now - self._last_rotation) if self._last_rotation else None

            return {
                "has_token": True,
                "expires_at": datetime.fromtimestamp(self._expires_at).isoformat() if self._expires_at else None,
                "time_until_expiry": time_until_expiry,
                "time_until_rotation": time_until_rotation
            }
