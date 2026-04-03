from __future__ import annotations
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

_NAME_FILE = Path.home() / ".saturn" / "instance_name"


def get_instance_name(base: str) -> str:
    if _NAME_FILE.exists():
        saved = _NAME_FILE.read_text().strip()
        if saved:
            return saved
    return base


def update_instance_name(new: str) -> None:
    _NAME_FILE.parent.mkdir(parents=True, exist_ok=True)
    _NAME_FILE.write_text(new)
    log.info("Instance name updated to %r", new)


def next_name(name: str) -> str:
    m = re.match(r"^(.*) \((\d+)\)$", name)
    if m:
        return f"{m.group(1)} ({int(m.group(2)) + 1})"
    return f"{name} (2)"
