from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Protocol, runtime_checkable


@dataclass
class ServiceRecord:
    name: str
    node_id: str
    host: str
    port: int
    txt: dict[str, str]
    addresses: list[str] = field(default_factory=list)


@dataclass
class AdvertiseSpec:
    name: str
    port: int
    txt: dict[str, str]
    subtypes: list[str] = field(default_factory=list)
    ttl: int | None = None


ServiceEvent = tuple[str, ServiceRecord]


@runtime_checkable
class MdnsBackend(Protocol):
    def advertise(self, spec: AdvertiseSpec) -> None: ...
    def withdraw(self) -> None: ...
    def browse(self, callback: Callable[[ServiceEvent], None]) -> None: ...
    def stop_browse(self) -> None: ...
    def close(self) -> None: ...
