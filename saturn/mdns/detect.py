from __future__ import annotations
import logging
import sys
import platform

log = logging.getLogger(__name__)


def select() -> str:
    if sys.platform == "darwin":
        return "bonjour"
    if sys.platform == "win32":
        build = int(platform.version().split(".")[-1])
        if build >= 17763:
            return "windows"
        return "userspace"
    try:
        import dbus
        dbus.SystemBus().get_object("org.freedesktop.Avahi", "/")
        return "avahi"
    except Exception:
        pass
    return "userspace"


def backend(name: str | None = None):
    chosen = name or select()
    if chosen == "bonjour":
        try:
            from saturn.mdns.bonjour import BonjourBackend
            return BonjourBackend()
        except ImportError:
            pass
    if chosen == "avahi":
        try:
            from saturn.mdns.avahi import AvahiBackend
            return AvahiBackend()
        except Exception:
            log.warning("Avahi backend unavailable, falling back to userspace")
            pass
    if chosen == "windows":
        try:
            from saturn.mdns.windows import WindowsBackend
            return WindowsBackend()
        except ImportError:
            pass
    if sys.platform == "darwin":
        log.warning(
            "Using userspace mDNS on macOS — responses sent from ephemeral "
            "ports violate RFC 6762 §11 and may be ignored by compliant "
            "implementations. Install the Bonjour backend for correct behavior."
        )
    from saturn.mdns.userspace import UserspaceBackend
    return UserspaceBackend()
