TXT_SAFE_CEILING = 1200


class TxtTooLarge(ValueError):
    pass


def validate(props: dict) -> int:
    total = 0
    for k, v in props.items():
        entry = f"{k}={v}".encode("utf-8")
        if len(entry) > 255:
            raise TxtTooLarge(
                f"TXT entry {k!r} value is {len(entry)} bytes (>255 RFC 6763 §6.1 cap per entry)"
            )
        total += 1 + len(entry)
        if total > TXT_SAFE_CEILING:
            raise TxtTooLarge(
                f"TXT total {total} bytes exceeds ceiling {TXT_SAFE_CEILING} (TXT_SAFE_CEILING)"
            )
    return total
