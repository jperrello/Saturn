import socket
from typing import List

import psutil


def routable_addrs() -> List[str]:
    out: List[str] = []
    stats = psutil.net_if_stats()
    for iface, addrs in psutil.net_if_addrs().items():
        st = stats.get(iface)
        if not st or not st.isup:
            continue
        for a in addrs:
            if a.family != socket.AF_INET:
                continue
            ip = a.address
            if not ip or ip.startswith("127.") or ip.startswith("169.254."):
                continue
            out.append(ip)
    return out
