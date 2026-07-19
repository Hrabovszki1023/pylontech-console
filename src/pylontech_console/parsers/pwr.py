from datetime import datetime, timezone
from types import MappingProxyType

from pylontech_console.domain.pwr import PwrPosition, PwrSummary

SUCCESS_CONFIRMATION = "Command completed successfully"
EXPECTED_COLUMNS = (
    "Power",
    "Volt",
    "Curr",
    "Tempr",
    "Tlow",
    "Thigh",
    "Vlow",
    "Vhigh",
    "Base.St",
    "Volt.St",
    "Curr.St",
    "Temp.St",
    "Coulomb",
    "Time",
    "B.V.St",
    "B.T.St",
    "MosTempr",
    "M.T.St",
)


class PwrParserError(ValueError):
    """Raised when an unindexed pwr payload violates its documented shape."""


def _optional_text(value: str) -> str | None:
    return None if value == "-" else value


def _optional_int(value: str, field_name: str) -> int | None:
    if value == "-":
        return None
    try:
        return int(value)
    except ValueError as error:
        raise PwrParserError(f"invalid {field_name}: {value!r}") from error


def _parse_soc(value: str) -> int | None:
    if value == "-":
        return None
    if not value.endswith("%"):
        raise PwrParserError(f"invalid Coulomb value: {value!r}")
    soc = _optional_int(value[:-1], "Coulomb")
    if soc is None or not 0 <= soc <= 100:
        raise PwrParserError(f"Coulomb value outside 0..100: {value!r}")
    return soc


def _parse_device_time(value: str) -> datetime | None:
    if value == "-":
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError as error:
        raise PwrParserError(f"invalid Time value: {value!r}") from error


def _logical_values(line: str) -> list[str]:
    tokens = line.split()
    if len(tokens) < 16:
        raise PwrParserError("pwr row has too few values")

    if tokens[13] == "-":
        time_value = "-"
        tail_start = 14
    else:
        if len(tokens) < 19:
            raise PwrParserError("pwr row has too few values")
        time_value = f"{tokens[13]} {tokens[14]}"
        tail_start = 15

    values = tokens[:13] + [time_value] + tokens[tail_start:]
    if len(values) == 16 and values[8] == "Absent":
        values.extend(("-", "-"))
    return values


def _parse_position(
    line: str,
    extra_columns: tuple[str, ...],
) -> PwrPosition:
    values = _logical_values(line)
    expected_value_count = len(EXPECTED_COLUMNS) + len(extra_columns)
    if len(values) < expected_value_count:
        raise PwrParserError("pwr row has too few values")
    if len(values) > expected_value_count:
        raise PwrParserError("pwr row has values without matching columns")

    try:
        position = int(values[0])
    except ValueError as error:
        raise PwrParserError(f"invalid Power value: {values[0]!r}") from error
    if not 1 <= position <= 16:
        raise PwrParserError(f"Power value outside 1..16: {position}")

    base_status = values[8]
    present = base_status != "Absent"
    if not present and any(
        value != "-" for index, value in enumerate(values[1:18], start=1) if index != 8
    ):
        raise PwrParserError(
            f"Absent position {position} contains a non-placeholder value",
        )

    extra_fields = MappingProxyType(
        dict(zip(extra_columns, values[len(EXPECTED_COLUMNS) :], strict=True)),
    )
    return PwrPosition(
        position=position,
        present=present,
        voltage_mv=_optional_int(values[1], "Volt"),
        current_ma=_optional_int(values[2], "Curr"),
        temperature_mc=_optional_int(values[3], "Tempr"),
        lowest_temperature_mc=_optional_int(values[4], "Tlow"),
        highest_temperature_mc=_optional_int(values[5], "Thigh"),
        lowest_cell_voltage_mv=_optional_int(values[6], "Vlow"),
        highest_cell_voltage_mv=_optional_int(values[7], "Vhigh"),
        base_status=base_status,
        voltage_status=_optional_text(values[9]),
        current_status=_optional_text(values[10]),
        temperature_status=_optional_text(values[11]),
        soc_percent=_parse_soc(values[12]),
        device_time=_parse_device_time(values[13]),
        battery_voltage_status=_optional_text(values[14]),
        battery_temperature_status=_optional_text(values[15]),
        mosfet_temperature_mc=_optional_int(values[16], "MosTempr"),
        mosfet_temperature_status=_optional_text(values[17]),
        extra_fields=extra_fields,
    )


def parse_pwr(payload: str, received_at: datetime) -> PwrSummary:
    """Parse one complete, unindexed pwr payload."""

    if received_at.tzinfo is None or received_at.utcoffset() is None:
        raise PwrParserError("received_at must be timezone-aware")

    lines = [line.strip() for line in payload.splitlines() if line.strip()]
    if not lines or lines[-1] != SUCCESS_CONFIRMATION:
        raise PwrParserError(
            "final non-empty payload line must be "
            f"{SUCCESS_CONFIRMATION!r}",
        )
    table_lines = lines[:-1]
    if not table_lines:
        raise PwrParserError("expected pwr table header is missing")
    if SUCCESS_CONFIRMATION in table_lines:
        raise PwrParserError(
            "success confirmation must be the final non-empty payload line",
        )

    header = tuple(table_lines[0].split())
    if header[: len(EXPECTED_COLUMNS)] != EXPECTED_COLUMNS:
        raise PwrParserError("expected pwr table header is missing")
    extra_columns = header[len(EXPECTED_COLUMNS) :]
    if len(set(extra_columns)) != len(extra_columns):
        raise PwrParserError("additional pwr column names must be unique")

    positions = tuple(
        _parse_position(line, extra_columns) for line in table_lines[1:]
    )
    if not positions:
        raise PwrParserError("pwr payload contains no position rows")
    position_numbers = [position.position for position in positions]
    if len(set(position_numbers)) != len(position_numbers):
        raise PwrParserError("pwr payload contains a duplicate position")

    return PwrSummary(
        received_at=received_at.astimezone(timezone.utc),
        positions=positions,
    )
