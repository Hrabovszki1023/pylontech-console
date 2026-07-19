from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class RackSummary:
    received_at: datetime
    state: str
    total_modules: int
    present_modules: int
    sleeping_modules: int
    voltage_mv: int
    current_ma: int
    remaining_capacity_mah: int
    full_charge_capacity_mah: int
    soc_percent: int
    soh_percent: int
    highest_cell_voltage_mv: int
    average_cell_voltage_mv: int
    lowest_cell_voltage_mv: int
    highest_temperature_mc: int
    average_temperature_mc: int
    lowest_temperature_mc: int
    recommended_charge_voltage_mv: int
    recommended_discharge_voltage_mv: int
    recommended_charge_current_ma: int
    recommended_discharge_current_ma: int
    system_recommended_charge_voltage_mv: int
    system_recommended_discharge_voltage_mv: int
    system_recommended_charge_current_ma: int
    system_recommended_discharge_current_ma: int
    extra_fields: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({}),
    )
    raw_payload: str = ""


@dataclass(frozen=True)
class ModuleDetail:
    received_at: datetime
    position: int
    voltage_mv: int
    current_ma: int
    temperature_mc: int
    soc_percent: int
    total_coulomb_mah: int
    max_voltage_mv: int
    charge_times: int
    basic_status: str
    discharge_seconds: int | None
    voltage_status: str
    current_status: str
    temperature_status: str
    coulomb_status: str
    soh_status: str
    heater_status: str
    enabled_protections: tuple[str, ...]
    battery_events_raw: str
    battery_events: int
    power_events_raw: str
    power_events: int
    system_fault_raw: str
    system_fault: int
    charge_seconds: int | None = None
    extra_fields: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({}),
    )
    raw_payload: str = ""


@dataclass(frozen=True)
class CellMeasurement:
    index: int
    voltage_mv: int
    current_ma: int
    temperature_mc: int
    base_status: str
    voltage_status: str
    current_status: str
    temperature_status: str
    soc_percent: int
    coulomb_mah: int
    balancing: str


@dataclass(frozen=True)
class ModuleCells:
    received_at: datetime
    position: int
    cells: tuple[CellMeasurement, ...]
    raw_payload: str = ""
