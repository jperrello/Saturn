import threading


class SettleDetector:
    def __init__(self, timeout=0.5):
        self._event = threading.Event()
        self._timer = None
        self._timeout = timeout

    def arm(self):
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(self._timeout, self._event.set)
        self._timer.daemon = True
        self._timer.start()

    def signal(self):
        if self._timer:
            self._timer.cancel()
        self._event.set()

    def wait(self, timeout=5.0):
        return self._event.wait(timeout=timeout)

    def close(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None
