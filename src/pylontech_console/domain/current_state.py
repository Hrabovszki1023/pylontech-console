from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from types import MappingProxyType
from typing import Generic, Mapping, TypeVar

from pylontech_console.domain.discovery import (
    InventoryState,
    TopologyEvent,
)
from pylontech_console.domain.process import ModuleCells, ModuleDetail, RackSummary

ValueT = TypeVar("ValueT")


class ConnectionState(str, Enum):
    STARTING = "starting"
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"


@dataclass(frozen=True)
class AcquisitionError:
    group: str
    detail: str
    timestamp: datetime
    barcode: str | None = None
    position: int | None = None


@dataclass(frozen=True)
class CurrentValue(Generic[ValueT]):
    value: ValueT | None
    received_at: datetime | None
    valid: bool
    interval_seconds: float
    stale_after_multiplier: float
    error: AcquisitionError | None = None

    def is_stale(self, now: datetime) -> bool:
        if self.received_at is None:
            return True
        return now >= self.received_at + timedelta(
            seconds=self.interval_seconds * self.stale_after_multiplier,
        )

    @classmethod
    def empty(
        cls,
        interval_seconds: float,
        stale_after_multiplier: float,
    ) -> "CurrentValue[ValueT]":
        return cls(
            value=None,
            received_at=None,
            valid=False,
            interval_seconds=interval_seconds,
            stale_after_multiplier=stale_after_multiplier,
        )


@dataclass(frozen=True)
class CurrentModule:
    detail: CurrentValue[ModuleDetail]
    cells: CurrentValue[ModuleCells]


@dataclass(frozen=True)
class CurrentState:
    updated_at: datetime | None
    connection: ConnectionState
    last_success_at: datetime | None
    consecutive_failures: int
    inventory: InventoryState
    inventory_freshness: CurrentValue[InventoryState]
    rack: CurrentValue[RackSummary]
    modules: Mapping[str, CurrentModule]
    topology_events: tuple[TopologyEvent, ...] = ()
    errors: tuple[AcquisitionError, ...] = ()

    @classmethod
    def empty(
        cls,
        rack_interval_seconds: float,
        module_interval_seconds: float,
        inventory_interval_seconds: float,
        stale_after_multiplier: float,
    ) -> "CurrentState":
        return cls(
            updated_at=None,
            connection=ConnectionState.STARTING,
            last_success_at=None,
            consecutive_failures=0,
            inventory=InventoryState.empty(),
            inventory_freshness=CurrentValue.empty(
                inventory_interval_seconds,
                stale_after_multiplier,
            ),
            rack=CurrentValue.empty(
                rack_interval_seconds,
                stale_after_multiplier,
            ),
            modules=MappingProxyType({}),
        )


def readonly_modules(
    values: Mapping[str, CurrentModule],
) -> Mapping[str, CurrentModule]:
    return MappingProxyType(dict(values))
