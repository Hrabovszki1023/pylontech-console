from datetime import datetime, timezone
from typing import Protocol

from pylontech_console.domain.info import ModuleIdentity
from pylontech_console.domain.process import ModuleCells, ModuleDetail, RackSummary
from pylontech_console.domain.pwr import PwrSummary
from pylontech_console.parsers.bat import parse_bat
from pylontech_console.parsers.info import parse_info
from pylontech_console.parsers.pwr import parse_pwr
from pylontech_console.parsers.pwr_detail import parse_pwr_detail
from pylontech_console.parsers.pwrsys import parse_pwrsys


class ReceiveClock(Protocol):
    def __call__(self) -> datetime: ...


class ConsoleExecutor(Protocol):
    async def execute(self, command: str) -> str: ...


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReadOnlyPylontechClient:
    """Typed production facade for the version 0.1 acquisition allowlist."""

    def __init__(
        self,
        console: ConsoleExecutor,
        clock: ReceiveClock = utc_now,
    ) -> None:
        self._console = console
        self._clock = clock

    async def read_topology(self) -> PwrSummary:
        payload = await self._console.execute("pwr")
        return parse_pwr(payload, self._clock())

    async def read_identity(self, position: int) -> ModuleIdentity:
        _validate_position(position)
        payload = await self._console.execute(f"info {position}")
        return parse_info(payload, self._clock(), position)

    async def read_rack(self) -> RackSummary:
        payload = await self._console.execute("pwrsys")
        return parse_pwrsys(payload, self._clock())

    async def read_module(self, position: int) -> ModuleDetail:
        _validate_position(position)
        payload = await self._console.execute(f"pwr {position}")
        return parse_pwr_detail(payload, self._clock(), position)

    async def read_cells(self, position: int) -> ModuleCells:
        _validate_position(position)
        payload = await self._console.execute(f"bat {position}")
        return parse_bat(payload, self._clock(), position)


def _validate_position(position: int) -> None:
    if not 1 <= position <= 16:
        raise ValueError("position outside 1..16")
