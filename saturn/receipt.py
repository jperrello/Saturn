"""Saturn-qj5.15 — per-turn applied-config receipt envelope.

CONFIG_RECEIPT_PATTERNS.md (gullivan): every assistant turn carries a
`saturn_meta` envelope so the user can see what config the upstream actually
applied — not what was configured. Six invariants pinned by qj5.15.
"""

import hashlib
import json
from typing import Any, Optional

SCHEMA_VERSION = 1

VERIFIABLE_FIELDS = {"max_tokens", "model", "finish_reason"}
UNVERIFIABLE_FIELDS = {"top_p", "top_k", "stop", "frequency_penalty", "presence_penalty"}


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def build_meta(
    configured: dict,
    applied: dict,
    system_prompt: Optional[str] = None,
    *,
    requested_model: Optional[str] = None,
) -> dict:
    coerced = []
    if requested_model and applied.get("model") and applied["model"] != requested_model:
        coerced.append("model")
    applied_out = {k: v for k, v in applied.items() if v is not None}
    if system_prompt:
        applied_out["system_prompt_sha256"] = _sha256(system_prompt)
        applied_out["system_prompt_preview"] = (system_prompt[:16] + "…") if len(system_prompt) > 16 else ""
    verif = {}
    for f in UNVERIFIABLE_FIELDS:
        if f in configured and configured[f] is not None:
            verif[f] = "requested-not-verifiable"
    return {
        "schema_version": SCHEMA_VERSION,
        "configured": {k: v for k, v in configured.items() if v is not None},
        "applied": applied_out,
        "verifiability": verif,
        "diff": {"coerced": coerced},
    }


def update_applied_from_chunk(applied: dict, line: str) -> None:
    if not line.startswith("data:"):
        return
    payload = line[5:].strip()
    if not payload or payload == "[DONE]":
        return
    try:
        obj = json.loads(payload)
    except Exception:
        return
    if not isinstance(obj, dict):
        return
    if obj.get("model"):
        applied["model"] = obj["model"]
    usage = obj.get("usage")
    if isinstance(usage, dict) and usage.get("completion_tokens") is not None:
        applied["usage"] = usage
    for c in obj.get("choices") or []:
        if isinstance(c, dict) and c.get("finish_reason"):
            applied["finish_reason"] = c["finish_reason"]


def emit_meta_line(configured: dict, applied: dict, system_prompt: Optional[str], requested_model: Optional[str]) -> str:
    meta = build_meta(configured, applied, system_prompt, requested_model=requested_model)
    return f'data: {json.dumps({"saturn_meta": meta})}\n\n'
