from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from pylontech_console.domain.info import ModuleIdentity
from pylontech_console.domain.pwr import PwrPosition


class TopologyEventKind(str, Enum):
    MODULE_DISCOVERED = "MODULE_DISCOVERED"
    MODULE_REMOVED = "MODULE_REMOVED"
    MODULE_REAPPEARED = "MODULE_REAPPEARED"
    MODULE_MOVED = "MODULE_MOVED"
    MODULE_REPLACED_AT_POSITION = "MODULE_REPLACED_AT_POSITION"
    INVENTORY_ERROR = "INVENTORY_ERROR"


class DiscoveryErrorKind(str, Enum):
    IDENTITY_READ_FAILED = "IDENTITY_READ_FAILED"
    POSITION_MISMATCH = "POSITION_MISMATCH"
    MISSING_BARCODE = "MISSING_BARCODE"
    DUPLICATE_BARCODE = "DUPLICATE_BARCODE"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    INCONSISTENT_INPUT = "INCONSISTENT_INPUT"


@dataclass(frozen=True)
class ModuleRecord:
    barcode: str
    identity: ModuleIdentity
    current_position: int | None
    present: bool | None
    first_seen_at: datetime
    last_seen_at: datetime
    power: PwrPosition | None


@dataclass(frozen=True)
class InventoryState:
    observed_at: datetime | None = None
    positions: Mapping[int, str] = field(
        default_factory=lambda: MappingProxyType({}),
    )
    modules: Mapping[str, ModuleRecord] = field(
        default_factory=lambda: MappingProxyType({}),
    )

    @classmethod
    def empty(cls) -> "InventoryState":
        return cls()


@dataclass(frozen=True)
class TopologyEvent:
    kind: TopologyEventKind
    timestamp: datetime
    detail: str
    barcode: str | None = None
    position: int | None = None
    previous_position: int | None = None
    replaced_barcode: str | None = None


@dataclass(frozen=True)
class DiscoveryError:
    kind: DiscoveryErrorKind
    detail: str
    position: int | None = None
    barcode: str | None = None


@dataclass(frozen=True)
class DiscoveryResult:
    state: InventoryState
    events: tuple[TopologyEvent, ...]
    errors: tuple[DiscoveryError, ...]
