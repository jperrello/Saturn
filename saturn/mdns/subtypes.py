from __future__ import annotations

ROLE_SUBTYPES: dict[str, str] = {
    "coordinator": "_coordinator",
    "worker": "_worker",
    "cloud": "_cloud",
    "beacon": "_beacon",
}


def subtypes_for_role(role: str) -> list[str]:
    sub = ROLE_SUBTYPES.get(role)
    return [sub] if sub else []
