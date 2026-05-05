from __future__ import annotations
import socket
import logging
import queue
import threading
from typing import Callable

from zeroconf import Zeroconf, ServiceBrowser, ServiceInfo, ServiceListener, NonUniqueNameException, IPVersion

from saturn.mdns.backend import MdnsBackend, AdvertiseSpec, ServiceRecord, ServiceEvent
from saturn.mdns.conflict import get_instance_name, update_instance_name, next_name

logger = logging.getLogger(__name__)

SERVICE_TYPE = "_saturn._tcp.local."


class _DualStackServiceInfo(ServiceInfo):
    @property
    def addresses(self):
        try:
            return list(self.addresses_by_version(IPVersion.All))
        except Exception:
            return list(self._ipv4_addresses or [])

    @addresses.setter
    def addresses(self, value):
        ServiceInfo.addresses.__set__(self, value)


def _parse_txt(properties: dict) -> dict[str, str]:
    txt = {}
    if not properties:
        return txt
    for k, v in properties.items():
        key = k.decode("utf-8") if isinstance(k, bytes) else k
        val = v.decode("utf-8") if isinstance(v, bytes) else str(v)
        txt[key] = val
    return txt


def _resolve(zc: Zeroconf, type_: str, name: str) -> ServiceRecord | None:
    info = zc.get_service_info(type_, name)
    if not info:
        return None
    raws: list[bytes] = []
    try:
        raws = list(info.addresses_by_version(IPVersion.All) or [])
    except Exception:
        raws = list(info.addresses or [])
    addrs: list[str] = []
    for raw in raws:
        try:
            if len(raw) == 4:
                addrs.append(socket.inet_ntoa(raw))
            elif len(raw) == 16:
                addrs.append(socket.inet_ntop(socket.AF_INET6, raw))
        except Exception:
            continue
    if addrs:
        host = addrs[0]
    elif info.server:
        host = info.server.rstrip(".")
    else:
        host = "unknown"
    txt = _parse_txt(info.properties)
    sname = name.replace(f".{type_}", "")
    return ServiceRecord(
        name=sname,
        node_id=txt.get("id", ""),
        host=host,
        port=info.port,
        txt=txt,
        addresses=addrs,
    )


_RESOLVE_WORKERS = 8
_STOP = object()


class _Listener(ServiceListener):
    def __init__(self, zc: Zeroconf, callback: Callable[[ServiceEvent], None]):
        self._zc = zc
        self._cb = callback
        self._q: queue.Queue = queue.Queue()
        self._inflight: set[str] = set()
        self._lock = threading.Lock()
        self._workers = [
            threading.Thread(target=self._run, name=f"saturn-resolve-{i}", daemon=True)
            for i in range(_RESOLVE_WORKERS)
        ]
        for w in self._workers:
            w.start()

    def _run(self) -> None:
        while True:
            item = self._q.get()
            if item is _STOP:
                self._q.task_done()
                return
            action, type_, name = item
            try:
                if action == "removed":
                    sname = name.replace(f".{type_}", "")
                    rec = ServiceRecord(name=sname, node_id="", host="", port=0, txt={})
                else:
                    rec = _resolve(self._zc, type_, name)
                if rec:
                    self._cb((action, rec))
            except Exception:
                logger.exception("resolve dispatch failed for %s %s", action, name)
            finally:
                with self._lock:
                    self._inflight.discard(f"{action}:{name}")
                self._q.task_done()

    def _dispatch(self, action: str, type_: str, name: str) -> None:
        key = f"{action}:{name}"
        with self._lock:
            if key in self._inflight:
                return
            self._inflight.add(key)
        self._q.put((action, type_, name))

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self._dispatch("added", type_, name)

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self._dispatch("updated", type_, name)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self._dispatch("removed", type_, name)

    def shutdown(self) -> None:
        for _ in self._workers:
            self._q.put(_STOP)


class UserspaceBackend:
    def __init__(self):
        self._zc = Zeroconf()
        self._info: ServiceInfo | None = None
        self._sub_infos: list[ServiceInfo] = []
        self._browser: ServiceBrowser | None = None
        self._listener: _Listener | None = None

    def advertise(self, spec: AdvertiseSpec) -> None:
        from saturn.discovery import get_lan_ip
        from saturn.mdns import interfaces as _ifaces
        try:
            ips = _ifaces.routable_addrs(family="both")
        except TypeError:
            ips = _ifaces.routable_addrs()
        if not ips:
            ips = [get_lan_ip()]
        name = get_instance_name(spec.name)
        addr = []
        for ip in ips:
            try:
                if ":" in ip:
                    addr.append(socket.inet_pton(socket.AF_INET6, ip))
                else:
                    addr.append(socket.inet_aton(ip))
            except OSError:
                continue
        server = f"{socket.gethostname()}.local."
        for _ in range(5):
            kwargs = dict(
                type_=SERVICE_TYPE,
                name=f"{name}.{SERVICE_TYPE}",
                port=spec.port,
                addresses=addr,
                server=server,
                properties=spec.txt,
            )
            if spec.ttl is not None:
                kwargs["other_ttl"] = spec.ttl
            self._info = _DualStackServiceInfo(**kwargs)
            try:
                self._zc.register_service(self._info)
                if name != spec.name:
                    update_instance_name(name)
                for sub in spec.subtypes:
                    sub_type = f"{sub}._sub._saturn._tcp.local."
                    sub_info = ServiceInfo(
                        type_=sub_type,
                        name=f"{name}.{sub_type}",
                        port=spec.port,
                        addresses=addr,
                        server=server,
                        properties=spec.txt,
                    )
                    self._zc.register_service(sub_info)
                    self._sub_infos.append(sub_info)
                return
            except NonUniqueNameException:
                logger.warning("mDNS name conflict for %r, trying next", name)
                name = next_name(name)
        logger.error("Could not register after 5 attempts; using last name %r", name)
        update_instance_name(name)

    def withdraw(self) -> None:
        for sub_info in self._sub_infos:
            try:
                self._zc.unregister_service(sub_info)
            except Exception:
                pass
        self._sub_infos = []
        if self._info:
            self._zc.unregister_service(self._info)
            self._info = None

    def browse(self, callback: Callable[[ServiceEvent], None]) -> None:
        self._listener = _Listener(self._zc, callback)
        self._browser = ServiceBrowser(self._zc, SERVICE_TYPE, self._listener)

    def stop_browse(self) -> None:
        if self._browser:
            self._browser.cancel()
            self._browser = None
        if self._listener:
            self._listener.shutdown()
            self._listener = None

    def close(self) -> None:
        self.withdraw()
        self.stop_browse()
        self._zc.close()
