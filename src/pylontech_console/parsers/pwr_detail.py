from datetime import datetime
from types import MappingProxyType

from pylontech_console.domain.process import ModuleDetail
from pylontech_console.parsers.common import (
    decimal,
    payload_lines,
    percent,
    utc_received_at,
)


class PwrDetailParserError(ValueError):
    """Raised when an indexed pwr payload violates its documented shape."""


REQUIRED = (
    "Voltage",
    "Current",
    "Temperature",
    "Coulomb",
    "Total Coulomb",
    "Max Voltage",
    "Charge Times",
    "Basic Status",
    "Volt Status",
    "Current Status",
    "Tmpr. Status",
    "Coul. Status",
    "Soh. Status",
    "Heater Status",
    "Protect ENA",
    "Bat Events",
    "Power Events",
    "System Fault",
)
REQUIRED_SET = frozenset(REQUIRED)
OPTIONAL_SET = frozenset(("Charge Sec.", "Discharge Sec."))
KNOWN_SET = REQUIRED_SET | OPTIONAL_SET


def _number(fields: dict[str, str], name: str) -> int:
    return decimal(fields[name].split()[0], name, PwrDetailParserError)


def _hex(fields: dict[str, str], name: str) -> tuple[str, int]:
    raw = fields[name]
    try:
        return raw, int(raw, 16)
    except ValueError as error:
        raise PwrDetailParserError(f"invalid {name}: {raw!r}") from error


def parse_pwr_detail(
    payload: str,
    received_at: datetime,
    expected_position: int,
) -> ModuleDetail:
    if not 1 <= expected_position <= 16:
        raise PwrDetailParserError("expected_position outside 1..16")
    lines = payload_lines(payload, PwrDetailParserError)
    received = utc_received_at(received_at, PwrDetailParserError)
    headings = [
        line
        for line in lines
        if len(line.split()) == 2
        and line.split()[0] == "Power"
        and line.split()[1].isdigit()
    ]
    if len(headings) != 1:
        raise PwrDetailParserError("indexed pwr payload must contain one Power heading")
    position = decimal(headings[0].split()[-1], "Power", PwrDetailParserError)
    if position != expected_position:
        raise PwrDetailParserError("returned Power does not match expected_position")

    fields: dict[str, str] = {}
    for line in lines:
        if line.startswith("-") or line in headings:
            continue
        if ":" not in line:
            raise PwrDetailParserError(f"indexed pwr line has no colon: {line!r}")
        name, value = (part.strip() for part in line.split(":", maxsplit=1))
        if name in fields:
            raise PwrDetailParserError(f"duplicate indexed pwr field: {name!r}")
        fields[name] = value
    missing = REQUIRED_SET.difference(fields)
    if missing:
        raise PwrDetailParserError(
            f"missing required indexed pwr fields: {', '.join(sorted(missing))}",
        )
    bat_raw, bat = _hex(fields, "Bat Events")
    power_raw, power = _hex(fields, "Power Events")
    fault_raw, fault = _hex(fields, "System Fault")
    return ModuleDetail(
        received_at=received,
        position=position,
        voltage_mv=_number(fields, "Voltage"),
        current_ma=_number(fields, "Current"),
        temperature_mc=_number(fields, "Temperature"),
        soc_percent=percent(fields["Coulomb"].split()[0], "Coulomb", PwrDetailParserError),
        total_coulomb_mah=_number(fields, "Total Coulomb"),
        max_voltage_mv=_number(fields, "Max Voltage"),
        charge_times=_number(fields, "Charge Times"),
        basic_status=fields["Basic Status"],
        voltage_status=fields["Volt Status"],
        current_status=fields["Current Status"],
        temperature_status=fields["Tmpr. Status"],
        coulomb_status=fields["Coul. Status"],
        soh_status=fields["Soh. Status"],
        heater_status=fields["Heater Status"],
        enabled_protections=tuple(fields["Protect ENA"].split()),
        battery_events_raw=bat_raw,
        battery_events=bat,
        power_events_raw=power_raw,
        power_events=power,
        system_fault_raw=fault_raw,
        system_fault=fault,
        charge_seconds=(
            _number(fields, "Charge Sec.") if "Charge Sec." in fields else None
        ),
        discharge_seconds=(
            _number(fields, "Discharge Sec.")
            if "Discharge Sec." in fields
            else None
        ),
        extra_fields=MappingProxyType(
            {name: value for name, value in fields.items() if name not in KNOWN_SET},
        ),
        raw_payload=payload,
    )
