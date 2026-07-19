from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pylontech_console.parsers.pwr import PwrParserError, parse_pwr

CAPTURE = (
    Path(__file__).parents[3] / "captures" / "US2000C" / "B67.5.0" / "pwr.txt"
)
HEADER = (
    "Power Volt Curr Tempr Tlow Thigh Vlow Vhigh Base.St Volt.St Curr.St "
    "Temp.St Coulomb Time B.V.St B.T.St MosTempr M.T.St"
)
PRESENT_ROW = (
    "1 49726 -3037 29300 26000 26600 3315 3316 Dischg Normal Normal Normal "
    "96% 2026-07-17 01:20:56 Normal Normal 27100 Normal"
)
ABSENT_ROW = "6 - - - - - - - Absent - - - - - - -"
RECEIVED_AT = datetime(2026, 7, 17, 3, 20, 57, tzinfo=timezone(timedelta(hours=2)))


def payload_with(*rows: str, header: str = HEADER) -> str:
    return "\n".join((header, *rows, "Command completed successfully"))


def canonical_payload() -> str:
    capture = CAPTURE.read_text(encoding="ascii")
    return capture.split("@", maxsplit=1)[1].split("$$", maxsplit=1)[0].strip()


def test_parses_canonical_capture() -> None:
    result = parse_pwr(canonical_payload(), RECEIVED_AT)

    assert len(result.positions) == 16
    assert sum(position.present for position in result.positions) == 5
    assert sum(not position.present for position in result.positions) == 11
    first = result.positions[0]
    assert first.position == 1
    assert first.voltage_mv == 49726
    assert first.current_ma == -3037
    assert first.temperature_mc == 29300
    assert first.lowest_temperature_mc == 26000
    assert first.highest_temperature_mc == 26600
    assert first.lowest_cell_voltage_mv == 3315
    assert first.highest_cell_voltage_mv == 3316
    assert first.soc_percent == 96
    assert first.mosfet_temperature_mc == 27100
    assert first.device_time == datetime(2026, 7, 17, 1, 20, 56)
    assert first.device_time.tzinfo is None

    absent = result.positions[5]
    assert not absent.present
    assert absent.base_status == "Absent"
    assert absent.voltage_mv is None
    assert absent.current_ma is None
    assert absent.device_time is None
    assert absent.voltage_status is None


def test_normalizes_one_shared_receive_time_to_utc() -> None:
    result = parse_pwr(payload_with(PRESENT_ROW, ABSENT_ROW), RECEIVED_AT)

    assert result.received_at == datetime(2026, 7, 17, 1, 20, 57, tzinfo=timezone.utc)
    assert result.received_at.tzinfo is timezone.utc


def test_rejects_naive_receive_time() -> None:
    with pytest.raises(PwrParserError, match="timezone-aware"):
        parse_pwr(payload_with(PRESENT_ROW), datetime(2026, 7, 17))


def test_accepts_positive_current() -> None:
    row = PRESENT_ROW.replace("-3037", "1250")

    result = parse_pwr(payload_with(row), RECEIVED_AT)

    assert result.positions[0].current_ma == 1250


@pytest.mark.parametrize(
    "payload",
    [
        f"{HEADER}\n{PRESENT_ROW}",
        f"{HEADER}\n{PRESENT_ROW}\nCommand completed successful",
        (
            f"{HEADER}\nCommand completed successfully\n{PRESENT_ROW}\n"
            "Command completed successfully"
        ),
        f"{HEADER}\n{PRESENT_ROW}\nCommand completed successfully\nunexpected",
    ],
)
def test_rejects_missing_altered_or_misplaced_confirmation(payload: str) -> None:
    with pytest.raises(PwrParserError, match="final non-empty"):
        parse_pwr(payload, RECEIVED_AT)


def test_rejects_missing_header() -> None:
    with pytest.raises(PwrParserError, match="header"):
        parse_pwr(f"{PRESENT_ROW}\nCommand completed successfully", RECEIVED_AT)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("49726", "invalid", "Volt"),
        ("96%", "invalid", "Coulomb"),
        ("96%", "101%", "outside"),
    ],
)
def test_rejects_malformed_numeric_and_soc(
    old: str,
    new: str,
    message: str,
) -> None:
    with pytest.raises(PwrParserError, match=message):
        parse_pwr(payload_with(PRESENT_ROW.replace(old, new)), RECEIVED_AT)


def test_rejects_duplicate_position() -> None:
    with pytest.raises(PwrParserError, match="duplicate"):
        parse_pwr(payload_with(PRESENT_ROW, PRESENT_ROW), RECEIVED_AT)


@pytest.mark.parametrize("position", ["0", "17"])
def test_rejects_out_of_range_position(position: str) -> None:
    row = PRESENT_ROW.replace("1 ", f"{position} ", 1)

    with pytest.raises(PwrParserError, match="outside"):
        parse_pwr(payload_with(row), RECEIVED_AT)


def test_rejects_missing_rows() -> None:
    with pytest.raises(PwrParserError, match="no position"):
        parse_pwr(payload_with(), RECEIVED_AT)


def test_rejects_short_row() -> None:
    with pytest.raises(PwrParserError, match="too few"):
        parse_pwr(payload_with("1 49726"), RECEIVED_AT)


def test_rejects_non_placeholder_value_in_absent_row() -> None:
    row = ABSENT_ROW.replace("6 -", "6 0", 1)

    with pytest.raises(PwrParserError, match="non-placeholder"):
        parse_pwr(payload_with(row), RECEIVED_AT)


def test_preserves_appended_columns() -> None:
    header = f"{HEADER} Firmware Flag"
    row = f"{PRESENT_ROW} B67.5.0 ready"

    result = parse_pwr(payload_with(row, header=header), RECEIVED_AT)

    assert dict(result.positions[0].extra_fields) == {
        "Firmware": "B67.5.0",
        "Flag": "ready",
    }
