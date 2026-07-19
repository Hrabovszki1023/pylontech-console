from datetime import datetime, timezone
from types import MappingProxyType

from pylontech_console.domain.info import ModuleIdentity

SUCCESS_CONFIRMATION = "Command completed successfully"
REQUIRED_FIELDS = (
    "Device address",
    "Manufacturer",
    "Device name",
    "Board version",
    "Main Soft version",
    "Soft version",
    "Boot version",
    "Comm version",
    "Release Date",
    "Barcode",
    "Specification",
    "Cell Number",
    "Max Dischg Curr",
    "Max Charge Curr",
    "EPONPort rate",
    "Console Port rate",
)
REQUIRED_FIELD_SET = frozenset(REQUIRED_FIELDS)


class InfoParserError(ValueError):
    """Raised when an info payload violates its documented shape."""


def _parse_integer(value: str, field_name: str) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise InfoParserError(f"invalid {field_name}: {value!r}") from error


def _parse_current(value: str, field_name: str) -> int:
    if not value.endswith("mA"):
        raise InfoParserError(f"invalid {field_name}: exact 'mA' suffix required")
    numeric_value = value[:-2]
    if not numeric_value:
        raise InfoParserError(f"invalid {field_name}: {value!r}")
    return _parse_integer(numeric_value, field_name)


def _normalized_field_name(value: str) -> str:
    return " ".join(value.split())


def _parse_fields(data_lines: list[str]) -> dict[str, str]:
    if not data_lines:
        raise InfoParserError("info payload contains no key/value records")

    fields: dict[str, str] = {}
    for line in data_lines:
        if ":" not in line:
            raise InfoParserError(f"info data line has no colon: {line!r}")
        raw_name, raw_value = line.split(":", maxsplit=1)
        name = _normalized_field_name(raw_name)
        if not name:
            raise InfoParserError("info field name must not be empty")
        if name in fields:
            raise InfoParserError(f"duplicate info field: {name!r}")
        fields[name] = raw_value.strip()

    missing_fields = REQUIRED_FIELD_SET.difference(fields)
    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise InfoParserError(f"missing required info fields: {missing}")
    return fields


def parse_info(
    payload: str,
    received_at: datetime,
    expected_position: int | None = None,
) -> ModuleIdentity:
    """Parse one complete local or indexed info payload."""

    if received_at.tzinfo is None or received_at.utcoffset() is None:
        raise InfoParserError("received_at must be timezone-aware")
    if expected_position is not None and not 1 <= expected_position <= 16:
        raise InfoParserError(
            f"expected_position outside 1..16: {expected_position}",
        )

    lines = [line.strip() for line in payload.splitlines() if line.strip()]
    if not lines or lines[-1] != SUCCESS_CONFIRMATION:
        raise InfoParserError(
            "final non-empty payload line must be "
            f"{SUCCESS_CONFIRMATION!r}",
        )
    if lines.count(SUCCESS_CONFIRMATION) != 1:
        raise InfoParserError(
            "success confirmation must occur exactly once as the final "
            "non-empty payload line",
        )

    fields = _parse_fields(lines[:-1])
    position = _parse_integer(fields["Device address"], "Device address")
    if not 1 <= position <= 16:
        raise InfoParserError(f"Device address outside 1..16: {position}")
    if expected_position is not None and position != expected_position:
        raise InfoParserError(
            "returned Device address does not match expected_position: "
            f"{position} != {expected_position}",
        )

    barcode = fields["Barcode"]
    if not barcode:
        raise InfoParserError("Barcode must not be empty")

    extra_fields = MappingProxyType(
        {
            name: value
            for name, value in fields.items()
            if name not in REQUIRED_FIELD_SET
        },
    )
    return ModuleIdentity(
        received_at=received_at.astimezone(timezone.utc),
        position=position,
        barcode=barcode,
        manufacturer=fields["Manufacturer"],
        device_name=fields["Device name"],
        board_version=fields["Board version"],
        main_software_version=fields["Main Soft version"],
        software_version=fields["Soft version"],
        boot_version=fields["Boot version"],
        communication_version=fields["Comm version"],
        release_date_raw=fields["Release Date"],
        specification=fields["Specification"],
        cell_count=_parse_integer(fields["Cell Number"], "Cell Number"),
        max_discharge_current_ma=_parse_current(
            fields["Max Dischg Curr"],
            "Max Dischg Curr",
        ),
        max_charge_current_ma=_parse_current(
            fields["Max Charge Curr"],
            "Max Charge Curr",
        ),
        epon_port_rate=_parse_integer(
            fields["EPONPort rate"],
            "EPONPort rate",
        ),
        console_port_rate=_parse_integer(
            fields["Console Port rate"],
            "Console Port rate",
        ),
        extra_fields=extra_fields,
        raw_payload=payload,
    )
