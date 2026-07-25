from dataclasses import replace
from datetime import datetime, timezone
from types import MappingProxyType

from fastapi import FastAPI

from pylontech_console.config import WebSettings
from pylontech_console.domain.current_state import (
    ConnectionState,
    CurrentModule,
    CurrentState,
    CurrentValue,
    readonly_modules,
)
from pylontech_console.domain.discovery import InventoryState, ModuleRecord
from pylontech_console.domain.info import ModuleIdentity
from pylontech_console.domain.process import (
    CellMeasurement,
    ModuleCells,
    ModuleDetail,
    RackSummary,
)
from pylontech_console.outputs.api import create_application
from pylontech_console.outputs.api.query import StateQuery
from pylontech_console.outputs.web import mount_web
from pylontech_console.polling import CurrentStateStore

SNAPSHOT_TIME = datetime(2026, 7, 25, 12, 0, 5, tzinfo=timezone.utc)
RECEIVED_TIME = datetime(2026, 7, 25, 12, 0, 0, tzinfo=timezone.utc)


def _identity(position: int, barcode: str) -> ModuleIdentity:
    return ModuleIdentity(
        received_at=RECEIVED_TIME,
        position=position,
        barcode=barcode,
        manufacturer="Pylon",
        device_name="US2000C",
        board_version="V10R04",
        main_software_version="B67.5.0",
        software_version="V1.7",
        boot_version="V2.0",
        communication_version="V2.0",
        release_date_raw="20-12-11",
        specification="48V/50AH",
        cell_count=15,
        max_discharge_current_ma=-90000,
        max_charge_current_ma=90000,
        epon_port_rate=1200,
        console_port_rate=115200,
    )


def _detail(position: int, voltage_mv: int) -> ModuleDetail:
    return ModuleDetail(
        RECEIVED_TIME, position, voltage_mv, 6500, 25000, 49, 50000,
        54000, 1, "Charge", None, "Normal", "Normal", "Normal", "Normal",
        "Normal", "OFF", (), "0x0", 0, "0x0", 0, "0x0", 0,
    )


def _cells(
    position: int,
    offset: int,
    voltages: tuple[int, ...] | None = None,
    voltage_statuses: tuple[str, ...] | None = None,
) -> ModuleCells:
    cell_voltages = voltages or tuple(
        3330 + ((index % 3) - 1) + offset
        for index in range(15)
    )
    statuses = voltage_statuses or ("Normal",) * 15
    return ModuleCells(
        RECEIVED_TIME,
        position,
        tuple(
            CellMeasurement(
                index=index,
                voltage_mv=voltage,
                current_ma=6500,
                temperature_mc=23500 + (index % 2) * 100,
                base_status="Charge",
                voltage_status=status,
                current_status="Normal",
                temperature_status="Normal",
                soc_percent=49,
                coulomb_mah=24500,
                balancing="Y" if index == 14 else "N",
            )
            for index, (voltage, status) in enumerate(
                zip(cell_voltages, statuses, strict=True),
            )
        ),
    )


def _rack() -> RackSummary:
    return RackSummary(
        RECEIVED_TIME, "System is charging", 2, 2, 0, 50000, 13000,
        98000, 200000, 49, 96, 3332, 3330, 3329, 26000, 24500, 23000,
        53250, 46000, 10000, -25000, 53250, 46000, 20000, -50000,
    )


def create_web_test_app(
    *,
    stale_second_module: bool = False,
    unsafe_barcode: str | None = None,
    first_module_voltages: tuple[int, ...] | None = None,
    first_voltage_statuses: tuple[str, ...] | None = None,
    web_settings: WebSettings | None = None,
) -> FastAPI:
    barcodes = (unsafe_barcode or "MODULE-A", "MODULE-B")
    records = {
        barcode: ModuleRecord(
            barcode=barcode,
            identity=_identity(position, barcode),
            current_position=position,
            present=True,
            first_seen_at=RECEIVED_TIME,
            last_seen_at=RECEIVED_TIME,
            power=None,
        )
        for position, barcode in enumerate(barcodes, 1)
    }
    inventory = InventoryState(
        observed_at=RECEIVED_TIME,
        positions=MappingProxyType({1: barcodes[0], 2: barcodes[1]}),
        modules=MappingProxyType(records),
    )
    modules = {
        barcode: CurrentModule(
            detail=CurrentValue(
                _detail(position, 49900 + position * 50),
                RECEIVED_TIME,
                True,
                60,
                2,
            ),
            cells=CurrentValue(
                _cells(
                    position,
                    position - 1,
                    first_module_voltages if position == 1 else None,
                    first_voltage_statuses if position == 1 else None,
                ),
                RECEIVED_TIME,
                True,
                1 if stale_second_module and position == 2 else 5,
                2,
            ),
        )
        for position, barcode in enumerate(barcodes, 1)
    }
    state = replace(
        CurrentState.empty(5, 60, 300, 2),
        updated_at=RECEIVED_TIME,
        connection=ConnectionState.ONLINE,
        last_success_at=RECEIVED_TIME,
        inventory=inventory,
        inventory_freshness=CurrentValue(
            inventory,
            RECEIVED_TIME,
            True,
            300,
            2,
        ),
        rack=CurrentValue(_rack(), RECEIVED_TIME, True, 5, 2),
        modules=readonly_modules(modules),
    )
    store = CurrentStateStore(state)
    query = StateQuery(store, clock=lambda: SNAPSHOT_TIME)
    app = create_application(store, query=query)
    app.state.current_state_store = store
    mount_web(app, query, web_settings)
    return app
