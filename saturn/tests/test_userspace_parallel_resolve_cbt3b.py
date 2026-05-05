"""Saturn-cbt.3.b — userspace parallel resolves.

Per DISCOVERY_AUDIT.md (b). `saturn/mdns/userspace.py:_Listener.add_service`
(line 55) calls `_resolve()` synchronously from zeroconf's listener thread.
This serializes all resolves onto one thread; under bursty advertisement N
adds back up at `Zeroconf.get_service_info()`'s 3s default timeout.

Falsifiable architectural oracle: when 12 services are advertised in quick
succession to a `UserspaceBackend.browse(...)` listener, the callbacks for
those `add` events MUST fire from at least 2 distinct OS threads. With the
current serial dispatch, all callbacks come from zeroconf's single engine
thread; after a `ThreadPoolExecutor`-based fix at userspace.py:55-63,
multiple worker threads carry the resolves.

NO MOCKS. Real `UserspaceBackend`, real `Zeroconf` advertisers on loopback.
"""

import socket
import threading
import time
import uuid

import pytest
from zeroconf import Zeroconf, ServiceInfo

from saturn.mdns.userspace import UserspaceBackend, SERVICE_TYPE


pytestmark = [pytest.mark.timeout(30), pytest.mark.slow]


@pytest.fixture
def advertiser_zc():
    z = Zeroconf(interfaces=["127.0.0.1"])
    yield z
    z.unregister_all_services()
    z.close()


def _register(zc, name, port):
    info = ServiceInfo(
        type_=SERVICE_TYPE,
        name=f"{name}.{SERVICE_TYPE}",
        port=port,
        addresses=[socket.inet_aton("127.0.0.1")],
        server=f"{name}.local.",
        properties={
            "version": "1.0",
            "deployment": "network",
            "api_type": "openai",
            "priority": "10",
            "models": "test-model",
            "capabilities": "chat",
            "context": "8192",
            "cost": "free",
        },
    )
    zc.register_service(info)
    return info


def test_userspace_resolves_run_on_multiple_threads(advertiser_zc):
    backend = UserspaceBackend()
    seen_threads: list[int] = []
    seen_names: list[str] = []
    seen_lock = threading.Lock()
    received = threading.Event()
    target = 8

    def cb(event):
        action, rec = event
        if action == "added":
            with seen_lock:
                seen_threads.append(threading.get_ident())
                seen_names.append(rec.name)
                if len(seen_names) >= target:
                    received.set()

    try:
        backend.browse(cb)

        names = [f"cbt3b-{uuid.uuid4().hex[:8]}-{i:02d}" for i in range(12)]
        for i, n in enumerate(names):
            _register(advertiser_zc, n, 9000 + i)

        assert received.wait(timeout=15.0), (
            f"only {len(seen_names)} of {target} expected adds arrived in 15s; "
            f"current implementation may be blocking on serial _resolve in the "
            f"zeroconf listener thread (saturn/mdns/userspace.py:55-63)"
        )

        with seen_lock:
            unique = set(seen_threads)

        assert len(unique) >= 2, (
            f"add_service callbacks fired from only {len(unique)} thread(s) "
            f"(idents={sorted(unique)!r}). _resolve() blocks the zeroconf engine "
            f"thread; dispatch resolves to a ThreadPoolExecutor at "
            f"saturn/mdns/userspace.py:55-63 so concurrent adds run in parallel. "
            f"Saw {len(seen_names)} adds total."
        )
    finally:
        backend.stop_browse()
        backend.close()
