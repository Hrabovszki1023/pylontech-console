from dataclasses import asdict, fields
from datetime import datetime

from pylontech_console.domain.current_state import (
    CurrentModule,
    CurrentState,
)
from pylontech_console.domain.discovery import ModuleRecord
from pylontech_console.domain.process import CellMeasurement
from pylontech_console.outputs.api.models import (
    CellCountModel,
    CellModel,
    CountModel,
    DetailValueModel,
    HealthModel,
    MetadataModel,
    RackDerivedModel,
    RackValueModel,
)
from pylontech_console.outputs.api.query import StateQuery
from pylontech_console.outputs.web.models import (
    HeatmapRow,
    ModulePage,
    RackPage,
    WebCell,
    WebModuleSummary,
)

EXPECTED_CELL_COUNT = 15


def _interpolate_channel(start: int, end: int, intensity: float) -> int:
    return round(start + ((end - start) * intensity))


def _cell_color(deviation: float, scale_limit: float) -> tuple[str, str]:
    if deviation == 0 or scale_limit == 0:
        return "#ffffff", "#172033"
    intensity = min(1.0, abs(deviation) / scale_limit)
    endpoint = (220, 58, 58) if deviation > 0 else (37, 99, 235)
    channels = tuple(
        _interpolate_channel(255, channel, intensity)
        for channel in endpoint
    )
    foreground = "#ffffff" if intensity >= 0.58 else "#172033"
    return f"rgb({channels[0]}, {channels[1]}, {channels[2]})", foreground


class WebQuery:
    """Create server-rendered view models from one shared state snapshot."""

    def __init__(self, query: StateQuery) -> None:
        self._query = query

    def _health(
        self,
        state: CurrentState,
        generated_at: datetime,
    ) -> HealthModel:
        details = [module.detail for module in state.modules.values()]
        cells = [module.cells for module in state.modules.values()]
        return HealthModel(
            generated_at=generated_at,
            status=state.connection.value,
            updated_at=state.updated_at,
            last_success_at=state.last_success_at,
            consecutive_failures=state.consecutive_failures,
            inventory=self._query.metadata(
                state.inventory_freshness,
                generated_at,
            ),
            rack=self._query.metadata(state.rack, generated_at),
            module_details=CountModel(
                total=len(details),
                valid=sum(value.valid for value in details),
                invalid=sum(not value.valid for value in details),
                stale=sum(value.is_stale(generated_at) for value in details),
            ),
            cell_groups=CellCountModel(
                module_groups=len(cells),
                total_cells=sum(
                    len(value.value.cells) if value.value is not None else 0
                    for value in cells
                ),
                valid_groups=sum(value.valid for value in cells),
                invalid_groups=sum(not value.valid for value in cells),
                stale_groups=sum(
                    value.is_stale(generated_at) for value in cells
                ),
            ),
            errors=[
                error
                for value in state.errors
                if (error := self._query.error(value)) is not None
            ],
        )

    @staticmethod
    def _rack_value(state: CurrentState) -> RackValueModel | None:
        value = state.rack.value
        if value is None:
            return None
        data = {
            field.name: getattr(value, field.name)
            for field in fields(value)
        }
        data.pop("raw_payload")
        data["extra_fields"] = dict(value.extra_fields)
        data["derived"] = RackDerivedModel(
            power_w=value.voltage_mv * value.current_ma / 1_000_000,
            cell_voltage_delta_mv=(
                value.highest_cell_voltage_mv
                - value.lowest_cell_voltage_mv
            ),
        )
        return RackValueModel.model_validate(data)

    def _summary(
        self,
        record: ModuleRecord,
        current: CurrentModule | None,
        generated_at: datetime,
    ) -> WebModuleSummary:
        empty = MetadataModel(
            received_at=None,
            age_seconds=None,
            valid=False,
            stale=True,
            error=None,
        )
        detail_metadata = (
            empty
            if current is None
            else self._query.metadata(current.detail, generated_at)
        )
        cell_metadata = (
            empty
            if current is None
            else self._query.metadata(current.cells, generated_at)
        )
        detail = (
            None if current is None or current.detail.value is None
            else current.detail.value
        )
        cell_values = (
            ()
            if current is None or current.cells.value is None
            else current.cells.value.cells
        )
        voltages = [cell.voltage_mv for cell in cell_values]
        return WebModuleSummary(
            barcode=record.barcode,
            position=record.current_position,
            present=record.present,
            model=record.identity.device_name,
            voltage_mv=None if detail is None else detail.voltage_mv,
            current_ma=None if detail is None else detail.current_ma,
            soc_percent=None if detail is None else detail.soc_percent,
            basic_status=None if detail is None else detail.basic_status,
            minimum_cell_voltage_mv=min(voltages) if voltages else None,
            maximum_cell_voltage_mv=max(voltages) if voltages else None,
            cell_voltage_delta_mv=(
                max(voltages) - min(voltages) if voltages else None
            ),
            detail_metadata=detail_metadata,
            cell_metadata=cell_metadata,
        )

    @staticmethod
    def _capture_is_current(
        current: CurrentModule | None,
        generated_at: datetime,
        expected_count: int,
    ) -> bool:
        return (
            current is not None
            and current.cells.value is not None
            and current.cells.valid
            and not current.cells.is_stale(generated_at)
            and len(current.cells.value.cells) == expected_count
        )

    @staticmethod
    def _row_cells(
        values: tuple[CellMeasurement, ...] | None,
        average: float | None,
        status: str,
        scale_limit: float,
    ) -> tuple[WebCell, ...]:
        by_index = {} if values is None else {
            cell.index: cell for cell in values
        }
        result: list[WebCell] = []
        for index in range(EXPECTED_CELL_COUNT):
            cell = by_index.get(index)
            if cell is None:
                result.append(
                    WebCell(
                        index=index,
                        voltage_mv=None,
                        deviation_mv=None,
                        status="unavailable",
                        background_color="#e5e7eb",
                        foreground_color="#4b5563",
                        accessible_label=f"Cell {index}: unavailable",
                    ),
                )
                continue
            deviation = (
                None if average is None else cell.voltage_mv - average
            )
            if status == "current" and deviation is not None:
                background, foreground = _cell_color(
                    deviation,
                    scale_limit,
                )
            else:
                background, foreground = "#e5e7eb", "#374151"
            result.append(
                WebCell(
                    index=index,
                    voltage_mv=cell.voltage_mv,
                    deviation_mv=deviation,
                    status=status,
                    background_color=background,
                    foreground_color=foreground,
                    accessible_label=(
                        f"Cell {index}: {cell.voltage_mv} millivolts, "
                        f"{status}"
                        if deviation is None
                        else (
                            f"Cell {index}: {cell.voltage_mv} millivolts, "
                            f"deviation {deviation:+.2f} millivolts, "
                            f"{status}"
                        )
                    ),
                ),
            )
        return tuple(result)

    def rack_page(self) -> RackPage:
        state, generated_at = self._query.snapshot()
        records = sorted(
            state.inventory.modules.values(),
            key=lambda record: (
                record.present is not True,
                record.current_position if record.current_position else 17,
                record.barcode,
            ),
        )
        modules = tuple(
            self._summary(
                record,
                state.modules.get(record.barcode),
                generated_at,
            )
            for record in records
        )

        row_data: list[
            tuple[
                ModuleRecord,
                CurrentModule | None,
                tuple[CellMeasurement, ...] | None,
                float | None,
                str,
            ]
        ] = []
        all_deviations: list[float] = []
        for record in records:
            if record.present is not True or record.current_position is None:
                continue
            current = state.modules.get(record.barcode)
            values = (
                None
                if current is None or current.cells.value is None
                else current.cells.value.cells
            )
            expected_count = record.identity.cell_count
            is_current = self._capture_is_current(
                current,
                generated_at,
                expected_count,
            )
            average = (
                sum(cell.voltage_mv for cell in values) / expected_count
                if is_current and values is not None
                else None
            )
            if average is not None and values is not None:
                all_deviations.extend(
                    cell.voltage_mv - average for cell in values
                )
            if current is None or current.cells.value is None:
                status = "unavailable"
            elif not current.cells.valid:
                status = "invalid"
            elif current.cells.is_stale(generated_at):
                status = "stale"
            else:
                status = "current"
            row_data.append((record, current, values, average, status))

        scale_limit = max(
            (abs(value) for value in all_deviations),
            default=0.0,
        )
        rows = tuple(
            HeatmapRow(
                barcode=record.barcode,
                position=record.current_position or 0,
                module_voltage_mv=(
                    None
                    if current is None or current.detail.value is None
                    else current.detail.value.voltage_mv
                ),
                module_average_cell_voltage_mv=average,
                status=status,
                cells=self._row_cells(
                    values,
                    average,
                    status,
                    scale_limit,
                ),
            )
            for record, current, values, average, status in row_data
        )
        health = self._health(state, generated_at)
        return RackPage(
            generated_at=generated_at,
            health=health,
            rack=self._rack_value(state),
            rack_metadata=self._query.metadata(state.rack, generated_at),
            modules=modules,
            heatmap_rows=rows,
            heatmap_scale_limit_mv=scale_limit,
            errors=tuple(health.errors),
        )

    def module_page(self, barcode: str) -> ModulePage | None:
        state, generated_at = self._query.snapshot()
        record = state.inventory.modules.get(barcode)
        if record is None:
            return None
        current = state.modules.get(barcode)
        empty = MetadataModel(
            received_at=None,
            age_seconds=None,
            valid=False,
            stale=True,
            error=None,
        )
        if current is None:
            detail_metadata = empty
            cell_metadata = empty
            detail_value = None
            cell_values = None
        else:
            detail_metadata = self._query.metadata(
                current.detail,
                generated_at,
            )
            cell_metadata = self._query.metadata(
                current.cells,
                generated_at,
            )
            detail_value = current.detail.value
            cell_values = (
                None
                if current.cells.value is None
                else tuple(
                    CellModel.model_validate(asdict(cell))
                    for cell in current.cells.value.cells
                )
            )
        detail = None
        if detail_value is not None:
            data = {
                field.name: getattr(detail_value, field.name)
                for field in fields(detail_value)
            }
            data.pop("raw_payload")
            data["extra_fields"] = dict(detail_value.extra_fields)
            data["enabled_protections"] = list(
                detail_value.enabled_protections,
            )
            detail = DetailValueModel.model_validate(data)
        voltages = (
            []
            if cell_values is None
            else [cell.voltage_mv for cell in cell_values]
        )
        return ModulePage(
            generated_at=generated_at,
            barcode=record.barcode,
            position=record.current_position,
            present=record.present,
            identity=self._query.identity(record.identity),
            detail=detail,
            detail_metadata=detail_metadata,
            cells=cell_values,
            cell_metadata=cell_metadata,
            minimum_cell_voltage_mv=min(voltages) if voltages else None,
            maximum_cell_voltage_mv=max(voltages) if voltages else None,
            cell_voltage_delta_mv=(
                max(voltages) - min(voltages) if voltages else None
            ),
        )
