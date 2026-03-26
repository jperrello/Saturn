from __future__ import annotations
import socket
import logging
import threading
from typing import Callable

from zeroconf import Zeroconf, ServiceBrowser, ServiceInfo, ServiceListener, NonUniqueNameException

from saturn.mdns.backend import MdnsBackend, AdvertiseSpec, ServiceRecord, ServiceEvent
from saturn.mdns.conflict import get_instance_name, update_instance_name, next_name

logger = logging.getLogger(__name__)

SERVICE_TYPE = "_saturn._tcp.local."


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
    try:
        if info.addresses:
            host = socket.inet_ntoa(info.addresses[0])
        else:
            host = info.server.rstrip(".")
    except Exception:
        host = info.server.rstrip(".") if info.server else "unknown"
    txt = _parse_txt(info.properties)
    sname = name.replace(f".{type_}", "")
    return ServiceRecord(
        name=sname,
        node_id=txt.get("id", ""),
        host=host,
        port=info.port,
        txt=txt,
    )


class _Listener(ServiceListener):
    def __init__(self, zc: Zeroconf, callback: Callable[[ServiceEvent], None]):
        self._zc = zc
        self._cb = callback

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        rec = _resolve(zc, type_, name)
        if rec:
            self._cb(("added", rec))

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        rec = _resolve(zc, type_, name)
        if rec:
            self._cb(("updated", rec))

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        sname = name.replace(f".{type_}", "")
        rec = ServiceRecord(name=sname, node_id="", host="", port=0, txt={})
        self._cb(("removed", rec))


class UserspaceBackend:
    def __init__(self):
        self._zc = Zeroconf()
        self._info: ServiceInfo | None = None
        self._browser: ServiceBrowser | None = None
        self._listener: _Listener | None = None

    def advertise(self, spec: AdvertiseSpec) -> None:
        from saturn.discovery import get_lan_ip
        host_ip = get_lan_ip()
        name = get_instance_name(spec.name)
        for _ in range(5):
            kwargs = dict(
                type_=SERVICE_TYPE,
                name=f"{name}.{SERVICE_TYPE}",
                port=spec.port,
                addresses=[socket.inet_aton(host_ip)],
                server=f"{socket.gethostname()}.local.",
                properties=spec.txt,
            )
            if spec.ttl is not None:
                kwargs["other_ttl"] = spec.ttl
            self._info = ServiceInfo(**kwargs)
            try:
                self._zc.register_service(self._info)
                if name != spec.name:
                    update_instance_name(name)
                return
            except NonUniqueNameException:
                logger.warning("mDNS name conflict for %r, trying next", name)
                name = next_name(name)
        logger.error("Could not register after 5 attempts; using last name %r", name)
        update_instance_name(name)

    def withdraw(self) -> None:
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
            self._listener = None

    def close(self) -> None:
        self.withdraw()
        self.stop_browse()
        self._zc.close()
