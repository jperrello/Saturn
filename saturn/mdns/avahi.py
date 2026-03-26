from __future__ import annotations
import logging
import threading
from typing import Callable

from saturn.mdns.backend import AdvertiseSpec, ServiceRecord, ServiceEvent

log = logging.getLogger(__name__)

SERVICE_TYPE = "_saturn._tcp"
AVAHI_IF_UNSPEC = -1
AVAHI_PROTO_UNSPEC = -1
AVAHI_PUBLISH_USE_MULTICAST = 16

AVAHI_SERVER_RUNNING = 2
AVAHI_SERVER_FAILURE = 5
AVAHI_CLIENT_FAILURE = 2
AVAHI_ENTRY_GROUP_COLLISION = 3
AVAHI_ENTRY_GROUP_FAILURE = 4

AVAHI_BROWSER_NEW = 0
AVAHI_BROWSER_REMOVE = 1
AVAHI_BROWSER_ALL_FOR_NOW = 2
AVAHI_BROWSER_FAILURE = 4

AVAHI_RESOLVER_FOUND = 0
AVAHI_RESOLVER_FAILURE = 1

AVAHI_LOOKUP_USE_MULTICAST = 2


def _decode(v) -> str:
    return v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else str(v)


def _parse_txt(raw) -> dict[str, str]:
    out = {}
    for item in raw:
        item = _decode(item)
        if "=" in item:
            k, _, v = item.partition("=")
            out[k] = v
        else:
            out[item] = ""
    return out


class AvahiBackend:
    def __init__(self):
        import dbus
        import dbus.mainloop.glib
        from gi.repository import GLib

        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self._bus = dbus.SystemBus()
        self._loop = GLib.MainLoop()
        self._thread = threading.Thread(target=self._loop.run, daemon=True)
        self._thread.start()

        server_obj = self._bus.get_object("org.freedesktop.Avahi", "/")
        self._server = dbus.Interface(server_obj, "org.freedesktop.Avahi.Server")
        self._server.connect_to_signal("StateChanged", self._on_server_state)
        self._group = None
        self._browser_obj = None
        self._spec: AdvertiseSpec | None = None
        self._fallback = None  # UserspaceBackend if daemon fails

    # ------------------------------------------------------------------
    # daemon failure fallback
    # ------------------------------------------------------------------

    def _on_server_state(self, state, error):
        if state == AVAHI_SERVER_FAILURE:
            log.warning("Avahi daemon failure (%s) — falling back to userspace mDNS", error)
            from saturn.mdns.userspace import UserspaceBackend
            self._fallback = UserspaceBackend()
            if self._spec:
                self._fallback.advertise(self._spec)

    # ------------------------------------------------------------------
    # advertise
    # ------------------------------------------------------------------

    def advertise(self, spec: AdvertiseSpec) -> None:
        if self._fallback:
            self._fallback.advertise(spec)
            return
        import dbus
        from saturn.mdns.conflict import get_instance_name, update_instance_name, next_name

        self._spec = spec
        name = get_instance_name(spec.name)

        for _ in range(5):
            group_path = self._server.EntryGroupNew()
            group_obj = self._bus.get_object("org.freedesktop.Avahi", group_path)
            group = dbus.Interface(group_obj, "org.freedesktop.Avahi.EntryGroup")

            txt = dbus.Array(
                [dbus.ByteArray(f"{k}={v}".encode()) for k, v in spec.txt.items()],
                signature="ay",
            )
            group.AddService(
                AVAHI_IF_UNSPEC,
                AVAHI_PROTO_UNSPEC,
                dbus.UInt32(0),
                name,
                SERVICE_TYPE,
                "",
                "",
                dbus.UInt16(spec.port),
                txt,
            )
            for sub in spec.subtypes:
                group.AddServiceSubtype(
                    AVAHI_IF_UNSPEC,
                    AVAHI_PROTO_UNSPEC,
                    dbus.UInt32(0),
                    name,
                    SERVICE_TYPE,
                    "",
                    sub,
                )

            group.connect_to_signal("StateChanged", self._on_group_state)
            try:
                group.Commit()
                self._group = group
                if name != spec.name:
                    update_instance_name(name)
                return
            except Exception as e:
                if "collision" in str(e).lower() or "COLLISION" in str(e):
                    log.warning("Avahi name conflict for %r, trying next", name)
                    name = next_name(name)
                else:
                    raise

        log.error("Could not register after 5 attempts, using %r", name)
        update_instance_name(name)

    def _on_group_state(self, state, error):
        if state == AVAHI_ENTRY_GROUP_COLLISION:
            log.warning("Avahi EntryGroup collision, re-advertising")
            if self._spec and self._group:
                from saturn.mdns.conflict import next_name, update_instance_name, get_instance_name
                name = get_instance_name(self._spec.name)
                new = next_name(name)
                update_instance_name(new)
                self._group.Reset()
                old_spec = self._spec
                self._group = None
                self.advertise(old_spec)
        elif state == AVAHI_ENTRY_GROUP_FAILURE:
            log.error("Avahi EntryGroup failure: %s", error)

    # ------------------------------------------------------------------
    # withdraw / close
    # ------------------------------------------------------------------

    def withdraw(self) -> None:
        if self._fallback:
            self._fallback.withdraw()
            return
        if self._group:
            try:
                self._group.Reset()
            except Exception:
                pass
            self._group = None

    def close(self) -> None:
        if self._fallback:
            self._fallback.close()
        self.withdraw()
        self.stop_browse()
        try:
            self._loop.quit()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # browse
    # ------------------------------------------------------------------

    def browse(self, callback: Callable[[ServiceEvent], None]) -> None:
        if self._fallback:
            self._fallback.browse(callback)
            return
        import dbus
        self._cb = callback
        path = self._server.ServiceBrowserNew(
            AVAHI_IF_UNSPEC,
            AVAHI_PROTO_UNSPEC,
            SERVICE_TYPE,
            "",
            dbus.UInt32(0),
        )
        obj = self._bus.get_object("org.freedesktop.Avahi", path)
        self._browser_obj = dbus.Interface(obj, "org.freedesktop.Avahi.ServiceBrowser")
        self._browser_obj.connect_to_signal("ItemNew", self._on_new)
        self._browser_obj.connect_to_signal("ItemRemove", self._on_remove)
        self._browser_obj.connect_to_signal("AllForNow", self._on_all_for_now)
        self._browser_obj.connect_to_signal("Failure", self._on_browse_failure)
        self._settle = threading.Event()

    def _on_new(self, interface, protocol, name, stype, domain, flags):
        try:
            iface, proto, aname, atype, adomain, host, aprotocol, address, port, txt, aflags = \
                self._server.ResolveService(
                    interface, protocol, name, stype, domain,
                    AVAHI_PROTO_UNSPEC, dbus.UInt32(AVAHI_LOOKUP_USE_MULTICAST)
                )
            rec = ServiceRecord(
                name=str(name),
                node_id="",
                host=str(address),
                port=int(port),
                txt=_parse_txt(txt),
            )
            rec.node_id = rec.txt.get("id", "")
            self._cb(("added", rec))
        except Exception as e:
            log.warning("Avahi resolve failed for %r: %s", name, e)

    def _on_remove(self, interface, protocol, name, stype, domain, flags):
        rec = ServiceRecord(name=str(name), node_id="", host="", port=0, txt={})
        self._cb(("removed", rec))

    def _on_all_for_now(self):
        if hasattr(self, "_settle"):
            self._settle.set()

    def _on_browse_failure(self, error):
        log.error("Avahi browse failure: %s", error)

    def stop_browse(self) -> None:
        if self._fallback:
            self._fallback.stop_browse()
            return
        if self._browser_obj:
            try:
                self._browser_obj.Free()
            except Exception:
                pass
            self._browser_obj = None
