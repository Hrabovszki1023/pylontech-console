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


def _logical_values(line: str, header: tuple[str, ...]) -> list[str]:
    tokens = line.split()
    if len(tokens) < 2:
        raise PwrParserError("pwr row has too few values")

    time_index = header.index("Time")
    if len(tokens) <= time_index:
        raise PwrParserError("pwr row has too few values")
    if tokens[time_index] != "-":
        if len(tokens) <= time_index + 1:
            raise PwrParserError("pwr row has too few values")
        tokens = (
            tokens[:time_index]
            + [f"{tokens[time_index]} {tokens[time_index + 1]}"]
            + tokens[time_index + 2 :]
        )
    return tokens


def _position_number(value: str) -> int:
    try:
        position = int(value)
    except ValueError as error:
        raise PwrParserError(f"invalid Power value: {value!r}") from error
    if not 1 <= position <= 16:
        raise PwrParserError(f"Power value outside 1..16: {position}")
    return position


def _parse_absent_position(
    tokens: list[str],
    extra_columns: tuple[str, ...],
) -> PwrPosition:
    if len(tokens) < 9:
        raise PwrParserError("pwr row has too few values")
    position = _position_number(tokens[0])
    if tokens.count("Absent") != 1 or any(
        value not in {"-", "Absent"} for value in tokens[1:]
    ):
        raise PwrParserError(
            f"Absent position {position} contains a non-placeholder value",
        )
    return PwrPosition(
        position=position,
        present=False,
        voltage_mv=None,
        current_ma=None,
        temperature_mc=None,
        lowest_temperature_mc=None,
        highest_temperature_mc=None,
        lowest_cell_voltage_mv=None,
        highest_cell_voltage_mv=None,
        base_status="Absent",
        voltage_status=None,
        current_status=None,
        temperature_status=None,
        soc_percent=None,
        device_time=None,
        battery_voltage_status=None,
        battery_temperature_status=None,
        mosfet_temperature_mc=None,
        mosfet_temperature_status=None,
        extra_fields=MappingProxyType(
            {column: "-" for column in extra_columns},
        ),
    )


def _parse_position(
    line: str,
    header: tuple[str, ...],
    extra_columns: tuple[str, ...],
) -> PwrPosition:
    tokens = line.split()
    if "Absent" in tokens:
        return _parse_absent_position(tokens, extra_columns)

    values = _logical_values(line, header)
    if len(values) < len(header):
        raise PwrParserError("pwr row has too few values")
    if len(values) > len(header):
        raise PwrParserError("pwr row has values without matching columns")
    fields = dict(zip(header, values, strict=True))

    position = _position_number(fields["Power"])
    base_status = fields["Base.St"]

    extra_fields = MappingProxyType(
        {column: fields[column] for column in extra_columns},
    )
    return PwrPosition(
        position=position,
        present=True,
        voltage_mv=_optional_int(fields["Volt"], "Volt"),
        current_ma=_optional_int(fields["Curr"], "Curr"),
        temperature_mc=_optional_int(fields["Tempr"], "Tempr"),
        lowest_temperature_mc=_optional_int(fields["Tlow"], "Tlow"),
        highest_temperature_mc=_optional_int(fields["Thigh"], "Thigh"),
        lowest_cell_voltage_mv=_optional_int(fields["Vlow"], "Vlow"),
        highest_cell_voltage_mv=_optional_int(fields["Vhigh"], "Vhigh"),
        base_status=base_status,
        voltage_status=_optional_text(fields["Volt.St"]),
        current_status=_optional_text(fields["Curr.St"]),
        temperature_status=_optional_text(fields["Temp.St"]),
        soc_percent=_parse_soc(fields["Coulomb"]),
        device_time=_parse_device_time(fields["Time"]),
        battery_voltage_status=_optional_text(fields["B.V.St"]),
        battery_temperature_status=_optional_text(fields["B.T.St"]),
        mosfet_temperature_mc=_optional_int(fields["MosTempr"], "MosTempr"),
        mosfet_temperature_status=_optional_text(fields["M.T.St"]),
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
    required_columns = tuple(
        column for column in header if column in EXPECTED_COLUMNS
    )
    if required_columns != EXPECTED_COLUMNS:
        raise PwrParserError("expected pwr table header is missing")
    if len(set(header)) != len(header):
        raise PwrParserError("pwr column names must be unique")
    extra_columns = tuple(
        column for column in header if column not in EXPECTED_COLUMNS
    )

    positions = tuple(
        _parse_position(line, header, extra_columns)
        for line in table_lines[1:]
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
