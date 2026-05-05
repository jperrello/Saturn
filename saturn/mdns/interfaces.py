import socket
from typing import List

import psutil


def routable_addrs(family: str = "v4") -> List[str]:
    want_v4 = family in ("v4", "both")
    want_v6 = family in ("v6", "both")
    out: List[str] = []
    stats = psutil.net_if_stats()
    for iface, addrs in psutil.net_if_addrs().items():
        st = stats.get(iface)
        if not st or not st.isup:
            continue
        for a in addrs:
            ip = a.address
            if not ip:
                continue
            if a.family == socket.AF_INET and want_v4:
                if ip.startswith("127.") or ip.startswith("169.254."):
                    continue
                out.append(ip)
            elif a.family == socket.AF_INET6 and want_v6:
                bare = ip.split("%", 1)[0]
                if bare in ("::1", "::") or bare.startswith("fe80:") or bare.startswith("FE80:"):
                    continue
                out.append(bare)
    return out
