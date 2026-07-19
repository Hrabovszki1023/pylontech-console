from datetime import datetime
from types import MappingProxyType

from pylontech_console.domain.process import RackSummary
from pylontech_console.parsers.common import (
    decimal,
    payload_lines,
    percent,
    utc_received_at,
)


class PwrSysParserError(ValueError):
    """Raised when a pwrsys payload violates its documented shape."""


FIELD_NAMES = (
    "Total Num",
    "Present Num",
    "Sleep Num",
    "System Volt",
    "System Curr",
    "System RC",
    "System FCC",
    "System SOC",
    "System SOH",
    "Highest voltage",
    "Average voltage",
    "Lowest voltage",
    "Highest temperature",
    "Average temperature",
    "Lowest temperature",
    "Recommend chg voltage",
    "Recommend dsg voltage",
    "Recommend chg current",
    "Recommend dsg current",
    "system Recommend chg voltage",
    "system Recommend dsg voltage",
    "system Recommend chg current",
    "system Recommend dsg current",
)
FIELD_SET = frozenset(FIELD_NAMES)


def _number(value: str, name: str) -> int:
    return decimal(value.split()[0], name, PwrSysParserError)


def parse_pwrsys(payload: str, received_at: datetime) -> RackSummary:
    lines = payload_lines(payload, PwrSysParserError)
    received = utc_received_at(received_at, PwrSysParserError)
    state_lines = [line for line in lines if line.lower().startswith("system is ")]
    if len(state_lines) != 1:
        raise PwrSysParserError("pwrsys payload must contain one system state")

    fields: dict[str, str] = {}
    for line in lines:
        if line.startswith(("-", "Power System")) or line in state_lines:
            continue
        if ":" not in line:
            raise PwrSysParserError(f"pwrsys data line has no colon: {line!r}")
        name, value = (part.strip() for part in line.split(":", maxsplit=1))
        if name in fields:
            raise PwrSysParserError(f"duplicate pwrsys field: {name!r}")
        fields[name] = value
    missing = FIELD_SET.difference(fields)
    if missing:
        raise PwrSysParserError(
            f"missing required pwrsys fields: {', '.join(sorted(missing))}",
        )
    extra = MappingProxyType(
        {name: value for name, value in fields.items() if name not in FIELD_SET},
    )
    return RackSummary(
        received_at=received,
        state=state_lines[0],
        total_modules=_number(fields["Total Num"], "Total Num"),
        present_modules=_number(fields["Present Num"], "Present Num"),
        sleeping_modules=_number(fields["Sleep Num"], "Sleep Num"),
        voltage_mv=_number(fields["System Volt"], "System Volt"),
        current_ma=_number(fields["System Curr"], "System Curr"),
        remaining_capacity_mah=_number(fields["System RC"], "System RC"),
        full_charge_capacity_mah=_number(fields["System FCC"], "System FCC"),
        soc_percent=percent(fields["System SOC"].split()[0], "System SOC", PwrSysParserError),
        soh_percent=percent(fields["System SOH"].split()[0], "System SOH", PwrSysParserError),
        highest_cell_voltage_mv=_number(fields["Highest voltage"], "Highest voltage"),
        average_cell_voltage_mv=_number(fields["Average voltage"], "Average voltage"),
        lowest_cell_voltage_mv=_number(fields["Lowest voltage"], "Lowest voltage"),
        highest_temperature_mc=_number(fields["Highest temperature"], "Highest temperature"),
        average_temperature_mc=_number(fields["Average temperature"], "Average temperature"),
        lowest_temperature_mc=_number(fields["Lowest temperature"], "Lowest temperature"),
        recommended_charge_voltage_mv=_number(fields["Recommend chg voltage"], "Recommend chg voltage"),
        recommended_discharge_voltage_mv=_number(fields["Recommend dsg voltage"], "Recommend dsg voltage"),
        recommended_charge_current_ma=_number(fields["Recommend chg current"], "Recommend chg current"),
        recommended_discharge_current_ma=_number(fields["Recommend dsg current"], "Recommend dsg current"),
        system_recommended_charge_voltage_mv=_number(fields["system Recommend chg voltage"], "system Recommend chg voltage"),
        system_recommended_discharge_voltage_mv=_number(fields["system Recommend dsg voltage"], "system Recommend dsg voltage"),
        system_recommended_charge_current_ma=_number(fields["system Recommend chg current"], "system Recommend chg current"),
        system_recommended_discharge_current_ma=_number(fields["system Recommend dsg current"], "system Recommend dsg current"),
        extra_fields=extra,
        raw_payload=payload,
    )
