from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

ValueT = TypeVar("ValueT")


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorModel(ApiModel):
    group: str
    detail: str
    timestamp: datetime
    barcode: str | None = None
    position: int | None = None


class MetadataModel(ApiModel):
    received_at: datetime | None
    age_seconds: float | None
    valid: bool
    stale: bool
    error: ErrorModel | None


class CurrentValueModel(MetadataModel, Generic[ValueT]):
    generated_at: datetime
    value: ValueT | None


class RackDerivedModel(ApiModel):
    power_w: float
    cell_voltage_delta_mv: int


class RackValueModel(ApiModel):
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
    extra_fields: dict[str, str]
    derived: RackDerivedModel


class PositionModel(ApiModel):
    position: int
    barcode: str


class IdentityModel(ApiModel):
    manufacturer: str
    device_name: str
    board_version: str
    main_software_version: str
    software_version: str
    boot_version: str
    communication_version: str
    release_date: str
    specification: str
    cell_count: int
    max_discharge_current_ma: int
    max_charge_current_ma: int
    epon_port_rate: int
    console_port_rate: int
    extra_fields: dict[str, str]


class DetailValueModel(ApiModel):
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
    enabled_protections: list[str]
    battery_events_raw: str
    battery_events: int
    power_events_raw: str
    power_events: int
    system_fault_raw: str
    system_fault: int
    charge_seconds: int | None
    extra_fields: dict[str, str]


class CellModel(ApiModel):
    index: int
    voltage_mv: int
    current_ma: int
    temperature_mc: int
    soc_percent: int
    coulomb_mah: int
    balancing: str
    base_status: str
    voltage_status: str
    current_status: str
    temperature_status: str


class CompactDetailModel(MetadataModel):
    voltage_mv: int | None
    current_ma: int | None
    temperature_mc: int | None
    soc_percent: int | None
    basic_status: str | None


class CompactCellsDerivedModel(ApiModel):
    minimum_voltage_mv: int | None
    maximum_voltage_mv: int | None
    voltage_delta_mv: int | None
    minimum_temperature_mc: int | None
    maximum_temperature_mc: int | None


class CompactCellsModel(MetadataModel):
    count: int | None
    derived: CompactCellsDerivedModel


class ModuleSummaryModel(ApiModel):
    barcode: str
    position: int | None
    present: bool | None
    first_seen_at: datetime
    last_seen_at: datetime
    identity: IdentityModel
    detail: CompactDetailModel
    cells: CompactCellsModel


class ModulesModel(ApiModel):
    generated_at: datetime
    modules: list[ModuleSummaryModel]


class ModuleModel(ApiModel):
    generated_at: datetime
    barcode: str
    position: int | None
    present: bool | None
    first_seen_at: datetime
    last_seen_at: datetime
    identity: IdentityModel
    detail: CurrentValueModel[DetailValueModel]
    cells: CurrentValueModel[list[CellModel]]


class PositionDetailModel(ApiModel):
    generated_at: datetime
    position: int
    barcode: str
    module: ModuleSummaryModel


class CountModel(ApiModel):
    total: int
    valid: int
    invalid: int
    stale: int


class CellCountModel(ApiModel):
    module_groups: int
    total_cells: int
    valid_groups: int
    invalid_groups: int
    stale_groups: int


class HealthModel(ApiModel):
    generated_at: datetime
    status: str
    updated_at: datetime | None
    last_success_at: datetime | None
    consecutive_failures: int
    inventory: MetadataModel
    rack: MetadataModel
    module_details: CountModel
    cell_groups: CellCountModel
    errors: list[ErrorModel]


class TopologyEventModel(ApiModel):
    kind: str
    timestamp: datetime
    detail: str
    barcode: str | None
    position: int | None
    previous_position: int | None
    replaced_barcode: str | None


class TopologyEventsModel(ApiModel):
    generated_at: datetime
    events: list[TopologyEventModel]
