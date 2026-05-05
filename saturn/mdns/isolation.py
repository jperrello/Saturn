import socket
import threading
import time
from dataclasses import dataclass, field
from typing import List

from zeroconf import Zeroconf, ServiceBrowser, ServiceInfo, ServiceListener


PROBE_TYPE = "_saturn-probe._tcp.local."


@dataclass
class IsolationProbe:
    advertising: bool = False
    self_seen: bool = False
    peers_seen: int = 0
    ifaces_with_link: List[str] = field(default_factory=list)
    suspected_ap_isolation: bool = False
    diagnosis: str = ""


def _link_ifaces() -> List[str]:
    try:
        import psutil
    except ImportError:
        return []
    out = []
    stats = psutil.net_if_stats()
    for name, st in stats.items():
        if st.isup and name != "lo0" and not name.startswith("lo"):
            out.append(name)
    return out


def probe(timeout: float = 4.0) -> IsolationProbe:
    result = IsolationProbe()
    result.ifaces_with_link = _link_ifaces()

    probe_name = f"saturn-probe-{int(time.time() * 1000)}-{threading.get_ident()}"
    fqn = f"{probe_name}.{PROBE_TYPE}"
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    info = ServiceInfo(
        type_=PROBE_TYPE,
        name=fqn,
        port=port,
        addresses=[socket.inet_aton("127.0.0.1")],
        server=f"{probe_name}.local.",
        properties={"id": probe_name},
    )

    seen = threading.Event()
    peer_count = [0]
    seen_lock = threading.Lock()

    class L(ServiceListener):
        def add_service(self, zc, type_, name):
            with seen_lock:
                if name == fqn:
                    seen.set()
                else:
                    peer_count[0] += 1

        def update_service(self, zc, type_, name):
            self.add_service(zc, type_, name)

        def remove_service(self, zc, type_, name):
            pass

    zc = Zeroconf()
    browser = None
    try:
        try:
            zc.register_service(info)
            result.advertising = True
        except Exception as e:
            result.advertising = False
            result.diagnosis = f"advertise failed: {e}"
            return result

        browser = ServiceBrowser(zc, PROBE_TYPE, L())
        seen.wait(timeout=timeout)
        result.self_seen = seen.is_set()
        with seen_lock:
            result.peers_seen = peer_count[0]
    finally:
        if browser:
            browser.cancel()
        try:
            zc.unregister_service(info)
        except Exception:
            pass
        zc.close()

    if not result.self_seen and result.advertising and result.ifaces_with_link:
        result.suspected_ap_isolation = True
        result.diagnosis = "advertising on link-up interfaces but cannot see self — possible AP isolation or multicast block"
    elif not result.self_seen and not result.ifaces_with_link:
        result.diagnosis = "no link-up interfaces; mDNS cannot reach the network"
    elif not result.self_seen:
        result.diagnosis = "loopback round-trip failed; check zeroconf engine"
    else:
        result.diagnosis = "loopback healthy"
    return result
