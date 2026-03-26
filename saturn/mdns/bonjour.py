from __future__ import annotations
import ctypes
import logging
import select
import threading
from typing import Callable

from saturn.mdns.backend import AdvertiseSpec, ServiceRecord, ServiceEvent

log = logging.getLogger(__name__)

SERVICE_TYPE = "_saturn._tcp"
_LIBPATH = "/usr/lib/libSystem.B.dylib"

# DNS-SD error codes
kDNSServiceErr_NoError = 0
kDNSServiceErr_NameConflict = -65548
kDNSServiceErr_BadReference = -65563

# Flags
kDNSServiceFlagsAdd = 0x2
kDNSServiceFlagsMoreComing = 0x1

DNSServiceRef = ctypes.c_void_p
DNSServiceFlags = ctypes.c_uint32
DNSServiceErrorType = ctypes.c_int32


def _load() -> ctypes.CDLL:
    lib = ctypes.CDLL(_LIBPATH)

    lib.DNSServiceRegister.restype = DNSServiceErrorType
    lib.DNSServiceRegister.argtypes = [
        ctypes.POINTER(DNSServiceRef),  # sdRef
        DNSServiceFlags,                # flags
        ctypes.c_uint32,                # interfaceIndex
        ctypes.c_char_p,                # name
        ctypes.c_char_p,                # regtype
        ctypes.c_char_p,                # domain
        ctypes.c_char_p,                # host
        ctypes.c_uint16,                # port (network byte order)
        ctypes.c_uint16,                # txtLen
        ctypes.c_void_p,                # txtRecord
        ctypes.c_void_p,                # callBack
        ctypes.c_void_p,                # context
    ]

    lib.DNSServiceBrowse.restype = DNSServiceErrorType
    lib.DNSServiceBrowse.argtypes = [
        ctypes.POINTER(DNSServiceRef),
        DNSServiceFlags,
        ctypes.c_uint32,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]

    lib.DNSServiceResolve.restype = DNSServiceErrorType
    lib.DNSServiceResolve.argtypes = [
        ctypes.POINTER(DNSServiceRef),
        DNSServiceFlags,
        ctypes.c_uint32,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]

    lib.DNSServiceRefSockFD.restype = ctypes.c_int
    lib.DNSServiceRefSockFD.argtypes = [DNSServiceRef]

    lib.DNSServiceProcessResult.restype = DNSServiceErrorType
    lib.DNSServiceProcessResult.argtypes = [DNSServiceRef]

    lib.DNSServiceRefDeallocate.restype = None
    lib.DNSServiceRefDeallocate.argtypes = [DNSServiceRef]

    return lib


def _encode_txt(txt: dict[str, str]) -> tuple[bytes, int]:
    parts = []
    for k, v in txt.items():
        s = f"{k}={v}".encode()
        parts.append(bytes([len(s)]) + s)
    data = b"".join(parts) or b"\x00"
    return data, len(data)


def _htons(port: int) -> int:
    import socket
    return socket.htons(port)


_RegisterCallbackType = ctypes.CFUNCTYPE(
    None,
    DNSServiceRef,     # sdRef
    DNSServiceFlags,   # flags
    DNSServiceErrorType,  # errorCode
    ctypes.c_char_p,   # name
    ctypes.c_char_p,   # regtype
    ctypes.c_char_p,   # domain
    ctypes.c_void_p,   # context
)

_BrowseCallbackType = ctypes.CFUNCTYPE(
    None,
    DNSServiceRef,
    DNSServiceFlags,
    ctypes.c_uint32,   # interfaceIndex
    DNSServiceErrorType,
    ctypes.c_char_p,   # serviceName
    ctypes.c_char_p,   # regtype
    ctypes.c_char_p,   # replyDomain
    ctypes.c_void_p,   # context
)

_ResolveCallbackType = ctypes.CFUNCTYPE(
    None,
    DNSServiceRef,
    DNSServiceFlags,
    ctypes.c_uint32,   # interfaceIndex
    DNSServiceErrorType,
    ctypes.c_char_p,   # fullname
    ctypes.c_char_p,   # hosttarget
    ctypes.c_uint16,   # port (network byte order)
    ctypes.c_uint16,   # txtLen
    ctypes.POINTER(ctypes.c_uint8),  # txtRecord
    ctypes.c_void_p,   # context
)


def _parse_txt(txt_len: int, txt_ptr) -> dict[str, str]:
    out: dict[str, str] = {}
    if not txt_ptr or txt_len == 0:
        return out
    data = bytes(txt_ptr[:txt_len])
    i = 0
    while i < len(data):
        n = data[i]
        i += 1
        if n == 0 or i + n > len(data):
            break
        item = data[i:i + n].decode("utf-8", errors="replace")
        i += n
        if "=" in item:
            k, _, v = item.partition("=")
            out[k] = v
        else:
            out[item] = ""
    return out


class BonjourBackend:
    def __init__(self):
        self._lib = _load()
        self._reg_ref: DNSServiceRef | None = None
        self._sub_refs: list[DNSServiceRef] = []
        self._browse_ref: DNSServiceRef | None = None
        self._spec: AdvertiseSpec | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._reg_cb_keep = None   # prevent GC of ctypes callback
        self._sub_cb_keeps: list = []
        self._browse_cb_keep = None
        self._browse_event_thread: threading.Thread | None = None
        self._reg_event_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # advertise
    # ------------------------------------------------------------------

    def advertise(self, spec: AdvertiseSpec) -> None:
        from saturn.mdns.conflict import get_instance_name, update_instance_name, next_name
        self._spec = spec
        name = get_instance_name(spec.name)

        txt_data, txt_len = _encode_txt(spec.txt)

        ref = DNSServiceRef(None)

        def _reply(sdref, flags, err, rname, regtype, domain, ctx):
            if err == kDNSServiceErr_NameConflict:
                log.warning("Bonjour name conflict for %r — re-registering", rname)
                from saturn.mdns.conflict import next_name as nx, update_instance_name as upd, get_instance_name as gin
                current = gin(self._spec.name) if self._spec else (rname.decode() if rname else name)
                new = nx(current)
                upd(new)
                # Re-register on a background thread to avoid deadlock inside callback
                threading.Thread(target=self._reregister, daemon=True).start()
            elif err != kDNSServiceErr_NoError:
                log.error("DNSServiceRegister error %d", err)

        cb = _RegisterCallbackType(_reply)
        self._reg_cb_keep = cb

        err = self._lib.DNSServiceRegister(
            ctypes.byref(ref),
            0,                      # flags
            0,                      # interfaceIndex (all)
            name.encode(),
            SERVICE_TYPE.encode(),
            None,                   # domain (default)
            None,                   # host (default)
            _htons(spec.port),
            txt_len,
            txt_data,
            cb,
            None,
        )
        if err != kDNSServiceErr_NoError:
            raise OSError(f"DNSServiceRegister failed: {err}")

        self._reg_ref = ref
        if name != spec.name:
            update_instance_name(name)

        self._reg_event_thread = threading.Thread(
            target=self._run_ref, args=(ref, "advertise"), daemon=True
        )
        self._reg_event_thread.start()

        for sub in spec.subtypes:
            sub_type = f"{sub}._sub._saturn._tcp"
            sub_ref = DNSServiceRef(None)

            def _sub_reply(sdref, flags, err, rname, regtype, domain, ctx, _s=sub_type):
                if err != kDNSServiceErr_NoError:
                    log.warning("DNSServiceRegister subtype %r error %d", _s, err)

            sub_cb = _RegisterCallbackType(_sub_reply)
            self._sub_cb_keeps.append(sub_cb)

            serr = self._lib.DNSServiceRegister(
                ctypes.byref(sub_ref),
                0,
                0,
                name.encode(),
                sub_type.encode(),
                None,
                None,
                _htons(spec.port),
                txt_len,
                txt_data,
                sub_cb,
                None,
            )
            if serr == kDNSServiceErr_NoError:
                self._sub_refs.append(sub_ref)
                t = threading.Thread(
                    target=self._run_ref, args=(sub_ref, f"advertise-sub:{sub}"), daemon=True
                )
                t.start()
            else:
                log.warning("DNSServiceRegister subtype %r failed: %d", sub_type, serr)


    def _reregister(self) -> None:
        self.withdraw()
        if self._spec:
            self.advertise(self._spec)

    # ------------------------------------------------------------------
    # event loop helpers
    # ------------------------------------------------------------------

    def _run_ref(self, ref: DNSServiceRef, label: str) -> None:
        fd = self._lib.DNSServiceRefSockFD(ref)
        if fd < 0:
            log.error("Invalid fd for %s event loop", label)
            return
        while not self._stop.is_set():
            try:
                r, _, _ = select.select([fd], [], [], 0.5)
                if r:
                    err = self._lib.DNSServiceProcessResult(ref)
                    if err == kDNSServiceErr_BadReference:
                        log.warning("Bonjour bad reference in %s — recovering", label)
                        if label == "advertise" and self._spec:
                            threading.Thread(target=self._reregister, daemon=True).start()
                        return
                    elif err != kDNSServiceErr_NoError:
                        log.error("DNSServiceProcessResult error %d in %s", err, label)
                        return
            except Exception as e:
                log.error("Event loop error in %s: %s", label, e)
                return

    # ------------------------------------------------------------------
    # withdraw / close
    # ------------------------------------------------------------------

    def withdraw(self) -> None:
        with self._lock:
            ref = self._reg_ref
            self._reg_ref = None
            sub_refs = self._sub_refs[:]
            self._sub_refs = []
            self._sub_cb_keeps = []
        for sr in sub_refs:
            self._lib.DNSServiceRefDeallocate(sr)
        if ref:
            self._lib.DNSServiceRefDeallocate(ref)

    def close(self) -> None:
        self._stop.set()
        self.withdraw()
        self.stop_browse()

    # ------------------------------------------------------------------
    # browse
    # ------------------------------------------------------------------

    def browse(self, callback: Callable[[ServiceEvent], None]) -> None:
        self._cb = callback
        ref = DNSServiceRef(None)

        def _browse_reply(sdref, flags, iface, err, name, regtype, domain, ctx):
            if err != kDNSServiceErr_NoError:
                log.error("DNSServiceBrowse error %d", err)
                return
            is_add = bool(flags & kDNSServiceFlagsAdd)
            sname = name.decode("utf-8", errors="replace") if name else ""
            stype = regtype.decode("utf-8", errors="replace") if regtype else SERVICE_TYPE
            sdomain = domain.decode("utf-8", errors="replace") if domain else "local."
            if is_add:
                threading.Thread(
                    target=self._resolve_service,
                    args=(sname, stype, sdomain, iface),
                    daemon=True,
                ).start()
            else:
                rec = ServiceRecord(name=sname, node_id="", host="", port=0, txt={})
                self._cb(("removed", rec))

        cb = _BrowseCallbackType(_browse_reply)
        self._browse_cb_keep = cb

        err = self._lib.DNSServiceBrowse(
            ctypes.byref(ref),
            0,
            0,
            SERVICE_TYPE.encode(),
            None,
            cb,
            None,
        )
        if err != kDNSServiceErr_NoError:
            raise OSError(f"DNSServiceBrowse failed: {err}")

        self._browse_ref = ref
        self._browse_event_thread = threading.Thread(
            target=self._run_ref, args=(ref, "browse"), daemon=True
        )
        self._browse_event_thread.start()

    def _resolve_service(self, name: str, regtype: str, domain: str, iface: int) -> None:
        ref = DNSServiceRef(None)

        def _resolve_reply(sdref, flags, riface, err, fullname, host, port_nbo, txt_len, txt_ptr, ctx):
            if err != kDNSServiceErr_NoError:
                log.warning("DNSServiceResolve error %d for %r", err, name)
                return
            import socket
            h = host.decode("utf-8", errors="replace").rstrip(".") if host else ""
            p = socket.ntohs(port_nbo)
            txt = _parse_txt(txt_len, txt_ptr)
            rec = ServiceRecord(name=name, node_id=txt.get("id", ""), host=h, port=p, txt=txt)
            self._cb(("added", rec))

        # Keep cb alive for the duration of this call (local var, not shared)
        cb = _ResolveCallbackType(_resolve_reply)

        err = self._lib.DNSServiceResolve(
            ctypes.byref(ref),
            0,
            iface,
            name.encode(),
            regtype.encode(),
            domain.encode(),
            cb,
            None,
        )
        if err != kDNSServiceErr_NoError:
            log.warning("DNSServiceResolve start failed %d for %r", err, name)
            return

        fd = self._lib.DNSServiceRefSockFD(ref)
        if fd >= 0:
            try:
                r, _, _ = select.select([fd], [], [], 5.0)
                if r:
                    self._lib.DNSServiceProcessResult(ref)
            except Exception as e:
                log.warning("Resolve select error for %r: %s", name, e)
        self._lib.DNSServiceRefDeallocate(ref)

    def stop_browse(self) -> None:
        with self._lock:
            ref = self._browse_ref
            self._browse_ref = None
        if ref:
            self._lib.DNSServiceRefDeallocate(ref)
