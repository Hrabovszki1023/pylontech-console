from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pytest

from pylontech_console.parsers import (
    BatParserError,
    PwrDetailParserError,
    PwrSysParserError,
    parse_bat,
    parse_pwr_detail,
    parse_pwrsys,
)

CAPTURES = Path(__file__).parents[3] / "captures" / "US2000C" / "B67.5.0"
NOW = datetime(2026, 7, 19, 12, tzinfo=timezone.utc)


def payload(name: str) -> str:
    text = (CAPTURES / name).read_text(encoding="ascii")
    return text.split("@", maxsplit=1)[1].split("$$", maxsplit=1)[0].strip()


def test_parses_pwrsys_capture() -> None:
    result = parse_pwrsys(payload("pwrsys.txt"), NOW)

    assert result.received_at == NOW
    assert result.state == "System is discharging"
    assert result.present_modules == 5
    assert result.voltage_mv == 49777
    assert result.current_ma == -11164
    assert result.soc_percent == 93
    assert result.system_recommended_discharge_current_ma == -125000
    assert result.raw_payload == payload("pwrsys.txt")


@pytest.mark.parametrize("position", range(1, 6))
def test_parses_every_indexed_pwr_capture(position: int) -> None:
    result = parse_pwr_detail(payload(f"pwr-{position}.txt"), NOW, position)

    assert result.position == position
    assert result.current_ma < 0
    assert result.enabled_protections
    assert result.battery_events_raw == "0x0"
    assert result.battery_events == 0
    assert result.charge_seconds is None
    assert result.discharge_seconds is not None


def test_parses_charging_indexed_pwr_capture() -> None:
    result = parse_pwr_detail(payload("pwr-1-charge.txt"), NOW, 1)

    assert result.basic_status == "Charge"
    assert result.charge_seconds == 1306
    assert result.discharge_seconds is None


def test_parses_symbolic_power_event_capture() -> None:
    result = parse_pwr_detail(payload("pwr-2-charge-event.txt"), NOW, 2)

    assert result.power_events_raw == "0x2000     COULFULL"
    assert result.power_events == 0x2000


def test_indexed_pwr_allows_unknown_state_without_timer() -> None:
    changed = (
        payload("pwr-1-charge.txt")
        .replace("Basic Status    : Charge", "Basic Status    : Future")
        .replace(" Charge Sec.     : 1306    s\n", "")
    )

    result = parse_pwr_detail(changed, NOW, 1)

    assert result.basic_status == "Future"
    assert result.charge_seconds is None
    assert result.discharge_seconds is None


@pytest.mark.parametrize("position", range(1, 6))
def test_parses_every_bat_capture(position: int) -> None:
    result = parse_bat(payload(f"bat-{position}.txt"), NOW, position)

    assert result.position == position
    assert len(result.cells) == 15
    assert [cell.index for cell in result.cells] == list(range(15))
    assert all(cell.current_ma < 0 for cell in result.cells)


@pytest.mark.parametrize(
    ("parser", "error"),
    [
        (lambda value: parse_pwrsys(value, NOW), PwrSysParserError),
        (lambda value: parse_pwr_detail(value, NOW, 1), PwrDetailParserError),
        (lambda value: parse_bat(value, NOW, 1), BatParserError),
    ],
)
def test_requires_success_confirmation(
    parser: Callable[[str], object],
    error: type[ValueError],
) -> None:
    with pytest.raises(error, match="final non-empty"):
        parser("invalid")


def test_pwrsys_preserves_unknown_field() -> None:
    changed = payload("pwrsys.txt").replace(
        "Command completed successfully",
        "Future Field : raw value\nCommand completed successfully",
    )

    assert dict(parse_pwrsys(changed, NOW).extra_fields) == {
        "Future Field": "raw value",
    }


def test_indexed_pwr_rejects_wrong_position() -> None:
    with pytest.raises(PwrDetailParserError, match="does not match"):
        parse_pwr_detail(payload("pwr-1.txt"), NOW, 2)


def test_bat_rejects_non_contiguous_indices() -> None:
    changed = payload("bat-1.txt").replace("\n1        3316", "\n2        3316", 1)

    with pytest.raises(BatParserError, match="duplicate|contiguous"):
        parse_bat(changed, NOW, 1)


@pytest.mark.parametrize(
    "parser",
    [
        lambda: parse_pwrsys(payload("pwrsys.txt"), datetime(2026, 7, 19)),
        lambda: parse_pwr_detail(
            payload("pwr-1.txt"),
            datetime(2026, 7, 19),
            1,
        ),
        lambda: parse_bat(payload("bat-1.txt"), datetime(2026, 7, 19), 1),
    ],
)
def test_rejects_naive_receive_time(parser: Callable[[], object]) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        parser()
