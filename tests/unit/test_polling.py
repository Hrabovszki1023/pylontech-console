import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from pylontech_console.config import PollingSettings
from pylontech_console.domain.current_state import CurrentValue
from pylontech_console.domain.info import ModuleIdentity
from pylontech_console.domain.process import (
    CellMeasurement,
    ModuleCells,
    ModuleDetail,
    RackSummary,
)
from pylontech_console.domain.pwr import PwrPosition, PwrSummary
from pylontech_console.polling import PollingService

T1 = datetime(2026, 7, 19, 10, tzinfo=timezone.utc)


def power(position: int) -> PwrPosition:
    return PwrPosition(
        position=position,
        present=True,
        voltage_mv=50000,
        current_ma=-1000,
        temperature_mc=25000,
        lowest_temperature_mc=24000,
        highest_temperature_mc=26000,
        lowest_cell_voltage_mv=3300,
        highest_cell_voltage_mv=3310,
        base_status="Dischg",
        voltage_status="Normal",
        current_status="Normal",
        temperature_status="Normal",
        soc_percent=80,
        device_time=None,
        battery_voltage_status="Normal",
        battery_temperature_status="Normal",
        mosfet_temperature_mc=None,
        mosfet_temperature_status=None,
    )


def identity(position: int, barcode: str) -> ModuleIdentity:
    return ModuleIdentity(
        received_at=T1,
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


def rack() -> RackSummary:
    return RackSummary(
        T1, "System is discharging", 2, 2, 0, 50000, -2000, 80000,
        100000, 80, 95, 3310, 3305, 3300, 26000, 25000, 24000,
        53250, 46000, 10000, -25000, 53250, 46000, 20000, -50000,
    )


def detail(position: int) -> ModuleDetail:
    return ModuleDetail(
        T1, position, 50000, -1000, 25000, 80, 50000, 54000, 0,
        "Dischg", 0, "Normal", "Normal", "Normal", "Normal", "Normal",
        "OFF", (), "0x0", 0, "0x0", 0, "0x0", 0,
    )


def cells(position: int) -> ModuleCells:
    return ModuleCells(
        T1,
        position,
        (
            CellMeasurement(
                0, 3300, -1000, 25000, "Dischg", "Normal", "Normal",
                "Normal", 80, 40000, "N",
            ),
        ),
    )


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.active = 0
        self.maximum_active = 0
        self.fail_cells: set[int] = set()

    async def _enter(self, call: str) -> None:
        self.calls.append(call)
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        await asyncio.sleep(0)
        self.active -= 1

    async def read_topology(self) -> PwrSummary:
        await self._enter("pwr")
        return PwrSummary(T1, (power(1), power(2)))

    async def read_identity(self, position: int) -> ModuleIdentity:
        await self._enter(f"info {position}")
        return identity(position, f"B{position}")

    async def read_rack(self) -> RackSummary:
        await self._enter("pwrsys")
        return rack()

    async def read_module(self, position: int) -> ModuleDetail:
        await self._enter(f"pwr {position}")
        return detail(position)

    async def read_cells(self, position: int) -> ModuleCells:
        await self._enter(f"bat {position}")
        if position in self.fail_cells:
            raise RuntimeError("sensitive")
        return cells(position)


@pytest.mark.asyncio
async def test_initializes_inventory_before_process_polling() -> None:
    client = FakeClient()
    service = PollingService(client, PollingSettings(), clock=lambda: T1)

    await service.initialize()

    assert client.calls == ["pwr", "info 1", "info 2"]
    assert dict(service.store.get().inventory.positions) == {1: "B1", 2: "B2"}
    assert list(service.store.get().modules) == ["B1", "B2"]


@pytest.mark.asyncio
async def test_polling_is_serial_and_barcode_keyed() -> None:
    client = FakeClient()
    service = PollingService(client, PollingSettings(), clock=lambda: T1)
    await service.initialize()

    await asyncio.gather(
        service.run_rack_and_cells_once(),
        service.run_modules_once(),
    )

    state = service.store.get()
    assert client.maximum_active == 1
    assert state.rack.valid
    assert state.modules["B1"].detail.value == detail(1)
    assert state.modules["B2"].cells.value == cells(2)


@pytest.mark.asyncio
async def test_partial_cell_failure_keeps_other_module_valid() -> None:
    client = FakeClient()
    client.fail_cells.add(1)
    service = PollingService(client, PollingSettings(), clock=lambda: T1)
    await service.initialize()

    await service.run_rack_and_cells_once()

    state = service.store.get()
    assert not state.modules["B1"].cells.valid
    assert state.modules["B2"].cells.valid
    assert state.errors[0].detail == "cells acquisition failed"
    assert "sensitive" not in state.errors[0].detail
    with pytest.raises(TypeError):
        state.modules["other"] = state.modules["B1"]  # type: ignore[index]


@pytest.mark.asyncio
async def test_failure_preserves_last_value_and_later_recovers() -> None:
    client = FakeClient()
    now = [T1]
    service = PollingService(client, PollingSettings(), clock=lambda: now[0])
    await service.initialize()
    await service.run_rack_and_cells_once()
    successful = service.store.get().modules["B1"].cells

    client.fail_cells.add(1)
    now[0] = T1 + timedelta(seconds=5)
    await service.run_rack_and_cells_once()
    failed = service.store.get().modules["B1"].cells

    assert failed.value == successful.value
    assert failed.received_at == T1
    assert not failed.valid
    assert not failed.is_stale(now[0])

    client.fail_cells.clear()
    await service.run_rack_and_cells_once()
    recovered = service.store.get().modules["B1"].cells

    assert recovered.valid
    assert recovered.error is None


def test_freshness_uses_configured_multiplier_and_boundary() -> None:
    value = CurrentValue(
        value="data",
        received_at=T1,
        valid=True,
        interval_seconds=5,
        stale_after_multiplier=2,
    )

    assert not value.is_stale(T1 + timedelta(seconds=9.999))
    assert value.is_stale(T1 + timedelta(seconds=10))


@pytest.mark.asyncio
async def test_stop_cancels_all_polling_tasks() -> None:
    client = FakeClient()
    waits: list[float] = []

    async def blocked_sleep(seconds: float) -> None:
        waits.append(seconds)
        await asyncio.Event().wait()

    service = PollingService(
        client,
        PollingSettings(),
        clock=lambda: T1,
        sleep=blocked_sleep,
    )
    await service.start()
    for _ in range(50):
        if len(waits) == 3:
            break
        await asyncio.sleep(0)
    await service.stop()

    assert set(waits) == {5, 60, 300}
    assert service._tasks == []  # noqa: SLF001
