from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class ModuleIdentity:
    received_at: datetime
    position: int
    barcode: str
    manufacturer: str
    device_name: str
    board_version: str
    main_software_version: str
    software_version: str
    boot_version: str
    communication_version: str
    release_date_raw: str
    specification: str
    cell_count: int
    max_discharge_current_ma: int
    max_charge_current_ma: int
    epon_port_rate: int
    console_port_rate: int
    extra_fields: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({}),
    )
    raw_payload: str = ""
