from dataclasses import dataclass
from datetime import datetime

from pylontech_console.outputs.api.models import (
    CellModel,
    DetailValueModel,
    ErrorModel,
    HealthModel,
    IdentityModel,
    MetadataModel,
    RackValueModel,
)


@dataclass(frozen=True)
class WebCell:
    index: int
    voltage_mv: int | None
    deviation_mv: float | None
    status: str
    absolute_state: str
    absolute_label: str
    background_color: str
    foreground_color: str
    accessible_label: str


@dataclass(frozen=True)
class WebModuleSummary:
    barcode: str
    position: int | None
    present: bool | None
    model: str
    voltage_mv: int | None
    current_ma: int | None
    soc_percent: int | None
    basic_status: str | None
    minimum_cell_voltage_mv: int | None
    maximum_cell_voltage_mv: int | None
    cell_voltage_delta_mv: int | None
    detail_metadata: MetadataModel
    cell_metadata: MetadataModel


@dataclass(frozen=True)
class HeatmapRow:
    barcode: str
    position: int
    module_voltage_mv: int | None
    module_average_cell_voltage_mv: float | None
    status: str
    cells: tuple[WebCell, ...]


@dataclass(frozen=True)
class RackPage:
    generated_at: datetime
    health: HealthModel
    rack: RackValueModel | None
    rack_metadata: MetadataModel
    modules: tuple[WebModuleSummary, ...]
    heatmap_rows: tuple[HeatmapRow, ...]
    heatmap_scale_limit_mv: float
    heatmap_deadband_mv: float
    cell_low_warning_mv: int
    cell_low_critical_mv: int
    cell_high_balancing_mv: int
    cell_high_warning_mv: int
    errors: tuple[ErrorModel, ...]


@dataclass(frozen=True)
class ModulePage:
    generated_at: datetime
    barcode: str
    position: int | None
    present: bool | None
    identity: IdentityModel
    detail: DetailValueModel | None
    detail_metadata: MetadataModel
    cells: tuple[CellModel, ...] | None
    cell_metadata: MetadataModel
    minimum_cell_voltage_mv: int | None
    maximum_cell_voltage_mv: int | None
    cell_voltage_delta_mv: int | None
