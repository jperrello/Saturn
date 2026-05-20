REJECTED = {}


def check(name: str) -> str:
    return REJECTED.get(name, "")
