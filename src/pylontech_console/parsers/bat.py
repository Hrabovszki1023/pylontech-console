from datetime import datetime

from pylontech_console.domain.process import CellMeasurement, ModuleCells
from pylontech_console.parsers.common import (
    decimal,
    payload_lines,
    percent,
    utc_received_at,
)


class BatParserError(ValueError):
    """Raised when an indexed bat payload violates its documented shape."""


HEADER = (
    "Battery Volt Curr Tempr Base State Volt. State Curr. State Temp. State "
    "SOC Coulomb BAL"
)


def parse_bat(
    payload: str,
    received_at: datetime,
    expected_position: int,
) -> ModuleCells:
    if not 1 <= expected_position <= 16:
        raise BatParserError("expected_position outside 1..16")
    lines = payload_lines(payload, BatParserError)
    received = utc_received_at(received_at, BatParserError)
    if not lines or " ".join(lines[0].split()) != HEADER:
        raise BatParserError("expected bat table header is missing")

    cells: list[CellMeasurement] = []
    for line in lines[1:]:
        values = line.split()
        if len(values) != 12 or values[10] != "mAH":
            raise BatParserError("bat row has an invalid column shape")
        cells.append(
            CellMeasurement(
                index=decimal(values[0], "Battery", BatParserError),
                voltage_mv=decimal(values[1], "Volt", BatParserError),
                current_ma=decimal(values[2], "Curr", BatParserError),
                temperature_mc=decimal(values[3], "Tempr", BatParserError),
                base_status=values[4],
                voltage_status=values[5],
                current_status=values[6],
                temperature_status=values[7],
                soc_percent=percent(values[8], "SOC", BatParserError),
                coulomb_mah=decimal(values[9], "Coulomb", BatParserError),
                balancing=values[11],
            ),
        )
    if not cells:
        raise BatParserError("bat payload contains no cell rows")
    indices = [cell.index for cell in cells]
    if len(indices) != len(set(indices)):
        raise BatParserError("bat payload contains a duplicate cell index")
    if indices != list(range(len(indices))):
        raise BatParserError("bat cell indices must be contiguous and zero-based")
    return ModuleCells(
        received_at=received,
        position=expected_position,
        cells=tuple(cells),
        raw_payload=payload,
    )
