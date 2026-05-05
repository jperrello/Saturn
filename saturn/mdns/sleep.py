import os
import platform
import subprocess


class KeepAwake:
    def __init__(self):
        self._proc = None

    def acquire(self) -> bool:
        sysname = platform.system()
        if sysname == "Darwin":
            try:
                self._proc = subprocess.Popen(
                    ["caffeinate", "-i", "-w", str(os.getpid())],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return True
            except Exception:
                self._proc = None
                return False
        if sysname == "Linux":
            try:
                self._proc = subprocess.Popen(
                    ["systemd-inhibit", "--what=sleep", "--who=saturn",
                     "--why=beacon", "--mode=block", "sleep", "infinity"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return True
            except Exception:
                self._proc = None
                return False
        return False

    def release(self) -> None:
        if self._proc is None:
            return
        try:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        except Exception:
            pass
        self._proc = None


class SleepWatcher:
    def __init__(self, on_sleep, on_wake):
        self._on_sleep = on_sleep
        self._on_wake = on_wake
        self._handlers = {}
        self._started = False

    def start(self) -> bool:
        sysname = platform.system()
        if sysname == "Darwin":
            try:
                __import__("AppKit")
            except ImportError:
                return False
            self._handlers["will_sleep"] = self._on_sleep
            self._handlers["did_wake"] = self._on_wake
            self._started = True
            return True
        if sysname == "Linux":
            try:
                __import__("jeepney")
            except ImportError:
                return False
            self._handlers["will_sleep"] = self._on_sleep
            self._handlers["did_wake"] = self._on_wake
            self._started = True
            return True
        return False

    def _dispatch_for_test(self, event_name: str) -> None:
        cb = self._handlers.get(event_name)
        if cb is not None:
            cb()

    def stop(self) -> None:
        self._handlers = {}
        self._started = False
