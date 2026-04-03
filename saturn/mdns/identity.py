import uuid
from pathlib import Path

_ID_FILE = Path.home() / ".saturn" / "node_id"
_cache = None


def _valid(s: str) -> bool:
    if not s:
        return False
    try:
        uuid.UUID(s)
        return True
    except ValueError:
        return False


def get_node_id() -> str:
    global _cache
    if _cache:
        return _cache
    if _ID_FILE.exists():
        candidate = _ID_FILE.read_text().strip()
        if _valid(candidate):
            _cache = candidate
            return _cache
    nid = str(uuid.uuid4())
    _ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ID_FILE.write_text(nid)
    _cache = nid
    return nid
