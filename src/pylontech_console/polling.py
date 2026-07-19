import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import datetime, timezone
from typing import Protocol, TypeVar

from pylontech_console.config import PollingSettings
from pylontech_console.discovery import discover_modules
from pylontech_console.domain.current_state import (
    AcquisitionError,
    ConnectionState,
    CurrentModule,
    CurrentState,
    CurrentValue,
    readonly_modules,
)
from pylontech_console.domain.info import ModuleIdentity
from pylontech_console.domain.process import ModuleCells, ModuleDetail, RackSummary
from pylontech_console.domain.pwr import PwrSummary

ResultT = TypeVar("ResultT")


class PollingCommandClient(Protocol):
    async def read_topology(self) -> PwrSummary: ...

    async def read_identity(self, position: int) -> ModuleIdentity: ...

    async def read_rack(self) -> RackSummary: ...

    async def read_module(self, position: int) -> ModuleDetail: ...

    async def read_cells(self, position: int) -> ModuleCells: ...


class Clock(Protocol):
    def __call__(self) -> datetime: ...


class Sleeper(Protocol):
    async def __call__(self, seconds: float) -> None: ...


class CurrentStateStore:
    """Atomically publish immutable current-state snapshots."""

    def __init__(self, initial: CurrentState) -> None:
        self._state = initial

    def get(self) -> CurrentState:
        return self._state

    def publish(self, state: CurrentState) -> None:
        self._state = state


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def default_sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)


class PollingService:
    def __init__(
        self,
        client: PollingCommandClient,
        settings: PollingSettings,
        *,
        clock: Clock = utc_now,
        sleep: Sleeper = default_sleep,
        store: CurrentStateStore | None = None,
    ) -> None:
        self._client = client
        self._settings = settings
        self._clock = clock
        self._sleep = sleep
        self._command_lock = asyncio.Lock()
        self._cycle_lock = asyncio.Lock()
        self._tasks: list[asyncio.Task[None]] = []
        self._store = store or CurrentStateStore(
            CurrentState.empty(
                settings.rack_interval_seconds,
                settings.module_interval_seconds,
                settings.inventory_interval_seconds,
                settings.stale_after_multiplier,
            ),
        )

    @property
    def store(self) -> CurrentStateStore:
        return self._store

    async def _command(
        self,
        operation: Callable[[], Awaitable[ResultT]],
    ) -> ResultT:
        async with self._command_lock:
            return await operation()

    async def read_identity(self, position: int) -> ModuleIdentity:
        return await self._command(lambda: self._client.read_identity(position))

    def _error(
        self,
        group: str,
        *,
        barcode: str | None = None,
        position: int | None = None,
    ) -> AcquisitionError:
        return AcquisitionError(
            group=group,
            detail=f"{group} acquisition failed",
            timestamp=self._clock().astimezone(timezone.utc),
            barcode=barcode,
            position=position,
        )

    def _publish(
        self,
        state: CurrentState,
        errors: list[AcquisitionError],
        *,
        success_at: datetime | None,
    ) -> None:
        previous = self._store.get()
        failures = previous.consecutive_failures + 1 if errors else 0
        connection = (
            ConnectionState.ONLINE
            if not errors
            else ConnectionState.DEGRADED
        )
        self._store.publish(
            replace(
                state,
                updated_at=self._clock().astimezone(timezone.utc),
                connection=connection,
                last_success_at=(
                    success_at
                    if success_at is not None
                    else previous.last_success_at
                ),
                consecutive_failures=failures,
                errors=tuple(errors),
            ),
        )

    async def initialize(self) -> None:
        await self.run_inventory_once()

    async def run_inventory_once(self) -> None:
        async with self._cycle_lock:
            await self._run_inventory_once()

    async def _run_inventory_once(self) -> None:
        previous = self._store.get()
        try:
            topology = await self._command(self._client.read_topology)
            result = await discover_modules(
                topology,
                previous.inventory,
                self,
            )
        except Exception:
            error = self._error("inventory")
            self._publish(
                replace(
                    previous,
                    inventory_freshness=replace(
                        previous.inventory_freshness,
                        valid=False,
                        error=error,
                    ),
                ),
                [error],
                success_at=None,
            )
            return

        modules = dict(previous.modules)
        ordered_barcodes = tuple(
            dict.fromkeys(result.state.positions.values()),
        )
        current_barcodes = set(ordered_barcodes)
        for barcode in list(modules):
            if barcode not in current_barcodes:
                modules.pop(barcode)
        for barcode in ordered_barcodes:
            modules.setdefault(
                barcode,
                CurrentModule(
                    detail=CurrentValue.empty(
                        self._settings.module_interval_seconds,
                        self._settings.stale_after_multiplier,
                    ),
                    cells=CurrentValue.empty(
                        self._settings.rack_interval_seconds,
                        self._settings.stale_after_multiplier,
                    ),
                ),
            )
        errors = [
            AcquisitionError(
                group="inventory",
                detail=error.detail,
                timestamp=topology.received_at,
                barcode=error.barcode,
                position=error.position,
            )
            for error in result.errors
        ]
        state = replace(
            previous,
            inventory=result.state,
            inventory_freshness=CurrentValue(
                value=result.state,
                received_at=topology.received_at,
                valid=not errors,
                interval_seconds=self._settings.inventory_interval_seconds,
                stale_after_multiplier=self._settings.stale_after_multiplier,
                error=errors[0] if errors else None,
            ),
            modules=readonly_modules(modules),
            topology_events=(
                previous.topology_events + result.events
            )[-100:],
        )
        self._publish(state, errors, success_at=topology.received_at)

    async def run_rack_and_cells_once(self) -> None:
        async with self._cycle_lock:
            await self._run_rack_and_cells_once()

    async def _run_rack_and_cells_once(self) -> None:
        previous = self._store.get()
        errors: list[AcquisitionError] = []
        rack = previous.rack
        try:
            value = await self._command(self._client.read_rack)
            rack = CurrentValue(
                value=value,
                received_at=value.received_at,
                valid=True,
                interval_seconds=self._settings.rack_interval_seconds,
                stale_after_multiplier=self._settings.stale_after_multiplier,
            )
        except Exception:
            error = self._error("rack")
            errors.append(error)
            rack = replace(rack, valid=False, error=error)

        modules = dict(previous.modules)
        for position, barcode in previous.inventory.positions.items():
            current = modules[barcode]
            try:
                def read_cells() -> Awaitable[ModuleCells]:
                    return self._client.read_cells(position)

                cells = await self._command(
                    read_cells,
                )
                cell_value = CurrentValue(
                    value=cells,
                    received_at=cells.received_at,
                    valid=True,
                    interval_seconds=self._settings.rack_interval_seconds,
                    stale_after_multiplier=self._settings.stale_after_multiplier,
                )
            except Exception:
                error = self._error(
                    "cells",
                    barcode=barcode,
                    position=position,
                )
                errors.append(error)
                cell_value = replace(current.cells, valid=False, error=error)
            modules[barcode] = replace(current, cells=cell_value)
        success = rack.received_at if rack.valid else None
        self._publish(
            replace(previous, rack=rack, modules=readonly_modules(modules)),
            errors,
            success_at=success,
        )

    async def run_modules_once(self) -> None:
        async with self._cycle_lock:
            await self._run_modules_once()

    async def _run_modules_once(self) -> None:
        previous = self._store.get()
        errors: list[AcquisitionError] = []
        modules = dict(previous.modules)
        successful_at: datetime | None = None
        for position, barcode in previous.inventory.positions.items():
            current = modules[barcode]
            try:
                def read_module() -> Awaitable[ModuleDetail]:
                    return self._client.read_module(position)

                detail = await self._command(
                    read_module,
                )
                detail_value = CurrentValue(
                    value=detail,
                    received_at=detail.received_at,
                    valid=True,
                    interval_seconds=self._settings.module_interval_seconds,
                    stale_after_multiplier=self._settings.stale_after_multiplier,
                )
                successful_at = detail.received_at
            except Exception:
                error = self._error(
                    "module",
                    barcode=barcode,
                    position=position,
                )
                errors.append(error)
                detail_value = replace(current.detail, valid=False, error=error)
            modules[barcode] = replace(current, detail=detail_value)
        self._publish(
            replace(previous, modules=readonly_modules(modules)),
            errors,
            success_at=successful_at,
        )

    async def _loop(
        self,
        operation: Callable[[], Awaitable[None]],
        interval: float,
    ) -> None:
        while True:
            await operation()
            await self._sleep(interval)

    async def start(self) -> None:
        if self._tasks:
            return
        await self.initialize()
        self._tasks = [
            asyncio.create_task(
                self._loop(
                    self.run_rack_and_cells_once,
                    self._settings.rack_interval_seconds,
                ),
            ),
            asyncio.create_task(
                self._loop(
                    self.run_modules_once,
                    self._settings.module_interval_seconds,
                ),
            ),
            asyncio.create_task(
                self._loop(
                    self.run_inventory_once,
                    self._settings.inventory_interval_seconds,
                ),
            ),
        ]

    async def stop(self) -> None:
        tasks, self._tasks = self._tasks, []
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
