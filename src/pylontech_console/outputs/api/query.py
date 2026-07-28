from dataclasses import asdict, fields
from datetime import UTC, datetime
from typing import Protocol, TypeVar

from pylontech_console.domain.current_state import (
    AcquisitionError,
    CurrentModule,
    CurrentState,
    CurrentValue,
)
from pylontech_console.domain.discovery import ModuleRecord
from pylontech_console.domain.info import ModuleIdentity
from pylontech_console.console_session import (
    ConsoleSessionHealth,
    ConsoleSessionHealthStore,
    ConsoleSessionMode,
)
from pylontech_console.mqtt_health import MqttHealth, MqttHealthStore
from pylontech_console.outputs.api.models import (
    CellCountModel,
    CellModel,
    CompactCellsDerivedModel,
    CompactCellsModel,
    CompactDetailModel,
    ConsoleSessionHealthModel,
    CountModel,
    CurrentValueModel,
    DetailValueModel,
    ErrorModel,
    HealthModel,
    IdentityModel,
    MetadataModel,
    MqttHealthModel,
    ModuleModel,
    ModulesModel,
    ModuleSummaryModel,
    PositionDetailModel,
    PositionModel,
    RackDerivedModel,
    RackValueModel,
    TopologyEventModel,
    TopologyEventsModel,
)
from pylontech_console.polling import CurrentStateStore

ValueT = TypeVar("ValueT")


class Clock(Protocol):
    def __call__(self) -> datetime: ...


def utc_now() -> datetime:
    return datetime.now(UTC)


class StateQuery:
    """Shared output view models over one authoritative state snapshot."""

    def __init__(
        self,
        store: CurrentStateStore,
        clock: Clock = utc_now,
        mqtt_health: MqttHealthStore | None = None,
        console_health: ConsoleSessionHealthStore | None = None,
    ) -> None:
        self._store = store
        self._clock = clock
        self._mqtt_health = mqtt_health or MqttHealthStore()
        self._console_health = console_health or ConsoleSessionHealthStore(
            ConsoleSessionHealth(
                mode=ConsoleSessionMode.DEBUG,
                authenticated=True,
            ),
        )

    def snapshot(self) -> tuple[CurrentState, datetime]:
        return self._store.get(), self._clock().astimezone(UTC)

    @staticmethod
    def error(value: AcquisitionError | None) -> ErrorModel | None:
        return None if value is None else ErrorModel.model_validate(
            asdict(value),
        )

    def metadata(
        self,
        value: CurrentValue[ValueT],
        generated_at: datetime,
    ) -> MetadataModel:
        age = (
            None
            if value.received_at is None
            else max(0.0, (generated_at - value.received_at).total_seconds())
        )
        return MetadataModel(
            received_at=value.received_at,
            age_seconds=age,
            valid=value.valid,
            stale=value.is_stale(generated_at),
            error=self.error(value.error),
        )

    @staticmethod
    def identity(value: ModuleIdentity) -> IdentityModel:
        return IdentityModel(
            manufacturer=value.manufacturer,
            device_name=value.device_name,
            board_version=value.board_version,
            main_software_version=value.main_software_version,
            software_version=value.software_version,
            boot_version=value.boot_version,
            communication_version=value.communication_version,
            release_date=value.release_date_raw,
            specification=value.specification,
            cell_count=value.cell_count,
            max_discharge_current_ma=value.max_discharge_current_ma,
            max_charge_current_ma=value.max_charge_current_ma,
            epon_port_rate=value.epon_port_rate,
            console_port_rate=value.console_port_rate,
            extra_fields=dict(value.extra_fields),
        )

    def summary(
        self,
        record: ModuleRecord,
        current: CurrentModule | None,
        generated_at: datetime,
    ) -> ModuleSummaryModel:
        detail = current.detail if current is not None else None
        cells = current.cells if current is not None else None
        detail_meta = (
            self.metadata(detail, generated_at)
            if detail is not None
            else MetadataModel(
                received_at=None, age_seconds=None, valid=False, stale=True,
                error=None,
            )
        )
        cells_meta = (
            self.metadata(cells, generated_at)
            if cells is not None
            else MetadataModel(
                received_at=None, age_seconds=None, valid=False, stale=True,
                error=None,
            )
        )
        detail_value = detail.value if detail is not None else None
        cell_values = (
            cells.value.cells
            if cells is not None and cells.value is not None
            else None
        )
        voltages = [] if cell_values is None else [c.voltage_mv for c in cell_values]
        temperatures = (
            [] if cell_values is None else [c.temperature_mc for c in cell_values]
        )
        return ModuleSummaryModel(
            barcode=record.barcode,
            position=record.current_position,
            present=record.present,
            first_seen_at=record.first_seen_at,
            last_seen_at=record.last_seen_at,
            identity=self.identity(record.identity),
            detail=CompactDetailModel(
                **detail_meta.model_dump(),
                voltage_mv=None if detail_value is None else detail_value.voltage_mv,
                current_ma=None if detail_value is None else detail_value.current_ma,
                temperature_mc=(
                    None if detail_value is None else detail_value.temperature_mc
                ),
                soc_percent=None if detail_value is None else detail_value.soc_percent,
                basic_status=None if detail_value is None else detail_value.basic_status,
            ),
            cells=CompactCellsModel(
                **cells_meta.model_dump(),
                count=None if cell_values is None else len(cell_values),
                derived=CompactCellsDerivedModel(
                    minimum_voltage_mv=min(voltages) if voltages else None,
                    maximum_voltage_mv=max(voltages) if voltages else None,
                    voltage_delta_mv=(
                        max(voltages) - min(voltages) if voltages else None
                    ),
                    minimum_temperature_mc=(
                        min(temperatures) if temperatures else None
                    ),
                    maximum_temperature_mc=(
                        max(temperatures) if temperatures else None
                    ),
                ),
            ),
        )

    def health_for(
        self,
        state: CurrentState,
        now: datetime,
    ) -> HealthModel:
        details = [module.detail for module in state.modules.values()]
        cells = [module.cells for module in state.modules.values()]
        mqtt = self._mqtt_health.get()
        console_session = self._console_health.get()
        status = state.connection.value
        if (
            state.connection.value == "online"
            and mqtt.enabled
            and not mqtt.connected
        ):
            status = "degraded"
        if (
            state.connection.value in ("online", "discovering")
            and not console_session.authenticated
        ):
            status = "offline"
        return HealthModel(
            generated_at=now,
            status=status,
            updated_at=state.updated_at,
            last_success_at=state.last_success_at,
            consecutive_failures=state.consecutive_failures,
            inventory=self.metadata(state.inventory_freshness, now),
            rack=self.metadata(state.rack, now),
            module_details=CountModel(
                total=len(details),
                valid=sum(value.valid for value in details),
                invalid=sum(not value.valid for value in details),
                stale=sum(value.is_stale(now) for value in details),
            ),
            cell_groups=CellCountModel(
                module_groups=len(cells),
                total_cells=sum(
                    len(value.value.cells) if value.value is not None else 0
                    for value in cells
                ),
                valid_groups=sum(value.valid for value in cells),
                invalid_groups=sum(not value.valid for value in cells),
                stale_groups=sum(value.is_stale(now) for value in cells),
            ),
            mqtt=self.mqtt_model(mqtt),
            console_session=self.console_session_model(console_session),
            errors=[self.error(error) for error in state.errors],  # type: ignore[misc]
        )

    @staticmethod
    def mqtt_model(value: MqttHealth) -> MqttHealthModel:
        return MqttHealthModel(
            enabled=value.enabled,
            state=value.state.value,
            connected=value.connected,
            last_connected_at=value.last_connected_at,
            last_disconnected_at=value.last_disconnected_at,
            consecutive_failures=value.consecutive_failures,
            error=value.error,
        )

    @staticmethod
    def console_session_model(
        value: ConsoleSessionHealth,
    ) -> ConsoleSessionHealthModel:
        return ConsoleSessionHealthModel(
            mode=value.mode.value,
            authenticated=value.authenticated,
            last_authenticated_at=value.last_authenticated_at,
            error=value.error,
        )

    def health(self) -> HealthModel:
        state, now = self.snapshot()
        return self.health_for(state, now)

    def rack(self) -> CurrentValueModel[RackValueModel]:
        state, now = self.snapshot()
        metadata = self.metadata(state.rack, now)
        value = state.rack.value
        rack_value = None
        if value is not None:
            data = {
                field.name: getattr(value, field.name)
                for field in fields(value)
            }
            data.pop("raw_payload")
            data["extra_fields"] = dict(value.extra_fields)
            data["derived"] = RackDerivedModel(
                power_w=value.voltage_mv * value.current_ma / 1_000_000,
                cell_voltage_delta_mv=(
                    value.highest_cell_voltage_mv - value.lowest_cell_voltage_mv
                ),
            )
            rack_value = RackValueModel.model_validate(data)
        return CurrentValueModel[RackValueModel](
            generated_at=now,
            **metadata.model_dump(),
            value=rack_value,
        )

    def positions(self) -> CurrentValueModel[list[PositionModel]]:
        state, now = self.snapshot()
        metadata = self.metadata(state.inventory_freshness, now)
        value = (
            None
            if state.inventory_freshness.value is None
            else [
                PositionModel(position=position, barcode=barcode)
                for position, barcode in sorted(state.inventory.positions.items())
            ]
        )
        return CurrentValueModel[list[PositionModel]](
            generated_at=now, **metadata.model_dump(), value=value,
        )

    def modules(self) -> ModulesModel:
        state, now = self.snapshot()
        records = sorted(
            state.inventory.modules.values(),
            key=lambda item: (
                item.present is not True,
                item.current_position if item.present else 17,
                item.barcode,
            ),
        )
        return ModulesModel(
            generated_at=now,
            modules=[
                self.summary(record, state.modules.get(record.barcode), now)
                for record in records
            ],
        )

    def module(self, barcode: str) -> ModuleModel | None:
        state, now = self.snapshot()
        record = state.inventory.modules.get(barcode)
        if record is None:
            return None
        current = state.modules.get(barcode)
        if current is None:
            empty = MetadataModel(
                received_at=None,
                age_seconds=None,
                valid=False,
                stale=True,
                error=None,
            )
            return ModuleModel(
                generated_at=now,
                barcode=barcode,
                position=record.current_position,
                present=record.present,
                first_seen_at=record.first_seen_at,
                last_seen_at=record.last_seen_at,
                identity=self.identity(record.identity),
                detail=CurrentValueModel[DetailValueModel](
                    generated_at=now,
                    **empty.model_dump(),
                    value=None,
                ),
                cells=CurrentValueModel[list[CellModel]](
                    generated_at=now,
                    **empty.model_dump(),
                    value=None,
                ),
            )
        detail_metadata = self.metadata(current.detail, now)
        cell_metadata = self.metadata(current.cells, now)
        detail = current.detail.value
        detail_value = None
        if detail is not None:
            data = {
                field.name: getattr(detail, field.name)
                for field in fields(detail)
            }
            data.pop("raw_payload")
            data["extra_fields"] = dict(detail.extra_fields)
            data["enabled_protections"] = list(detail.enabled_protections)
            detail_value = DetailValueModel.model_validate(data)
        cell_value = (
            None
            if current.cells.value is None
            else [
                CellModel.model_validate(asdict(cell))
                for cell in current.cells.value.cells
            ]
        )
        return ModuleModel(
            generated_at=now,
            barcode=barcode,
            position=record.current_position,
            present=record.present,
            first_seen_at=record.first_seen_at,
            last_seen_at=record.last_seen_at,
            identity=self.identity(record.identity),
            detail=CurrentValueModel[DetailValueModel](
                generated_at=now,
                **detail_metadata.model_dump(),
                value=detail_value,
            ),
            cells=CurrentValueModel[list[CellModel]](
                generated_at=now,
                **cell_metadata.model_dump(),
                value=cell_value,
            ),
        )

    def position(self, position: int) -> PositionDetailModel | None:
        state, now = self.snapshot()
        barcode = state.inventory.positions.get(position)
        if barcode is None:
            return None
        record = state.inventory.modules[barcode]
        return PositionDetailModel(
            generated_at=now,
            position=position,
            barcode=barcode,
            module=self.summary(record, state.modules.get(barcode), now),
        )

    def topology_events(self, limit: int) -> TopologyEventsModel:
        state, now = self.snapshot()
        events = reversed(state.topology_events[-limit:])
        return TopologyEventsModel(
            generated_at=now,
            events=[
                TopologyEventModel(
                    kind=event.kind.value,
                    timestamp=event.timestamp,
                    detail=event.detail,
                    barcode=event.barcode,
                    position=event.position,
                    previous_position=event.previous_position,
                    replaced_barcode=event.replaced_barcode,
                )
                for event in events
            ],
        )
