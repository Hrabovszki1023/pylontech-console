from datetime import datetime, timezone

SUCCESS_CONFIRMATION = "Command completed successfully"


def utc_received_at(value: datetime, error_type: type[ValueError]) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise error_type("received_at must be timezone-aware")
    return value.astimezone(timezone.utc)


def payload_lines(payload: str, error_type: type[ValueError]) -> list[str]:
    lines = [line.strip() for line in payload.splitlines() if line.strip()]
    if not lines or lines[-1] != SUCCESS_CONFIRMATION:
        raise error_type(
            "final non-empty payload line must be "
            f"{SUCCESS_CONFIRMATION!r}",
        )
    if lines.count(SUCCESS_CONFIRMATION) != 1:
        raise error_type(
            "success confirmation must occur exactly once as the final "
            "non-empty payload line",
        )
    return lines[:-1]


def decimal(value: str, field_name: str, error_type: type[ValueError]) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise error_type(f"invalid {field_name}: {value!r}") from error


def percent(value: str, field_name: str, error_type: type[ValueError]) -> int:
    numeric = value[:-1] if value.endswith("%") else value
    result = decimal(numeric, field_name, error_type)
    if not 0 <= result <= 100:
        raise error_type(f"{field_name} outside 0..100: {value!r}")
    return result
