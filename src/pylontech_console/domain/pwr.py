from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class PwrPosition:
    position: int
    present: bool
    voltage_mv: int | None
    current_ma: int | None
    temperature_mc: int | None
    lowest_temperature_mc: int | None
    highest_temperature_mc: int | None
    lowest_cell_voltage_mv: int | None
    highest_cell_voltage_mv: int | None
    base_status: str
    voltage_status: str | None
    current_status: str | None
    temperature_status: str | None
    soc_percent: int | None
    device_time: datetime | None
    battery_voltage_status: str | None
    battery_temperature_status: str | None
    mosfet_temperature_mc: int | None
    mosfet_temperature_status: str | None
    extra_fields: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({}),
    )


@dataclass(frozen=True)
class PwrSummary:
    received_at: datetime
    positions: tuple[PwrPosition, ...]
