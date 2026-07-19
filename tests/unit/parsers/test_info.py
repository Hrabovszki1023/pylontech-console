from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pylontech_console.parsers.info import InfoParserError, parse_info

CAPTURE_DIRECTORY = (
    Path(__file__).parents[3] / "captures" / "US2000C" / "B67.5.0"
)
RECEIVED_AT = datetime(2026, 7, 17, 3, 20, 57, tzinfo=timezone(timedelta(hours=2)))


def capture_payload(name: str) -> str:
    capture = (CAPTURE_DIRECTORY / name).read_text(encoding="ascii")
    return capture.split("@", maxsplit=1)[1].split("$$", maxsplit=1)[0].strip()


def indexed_payload() -> str:
    return capture_payload("info-2.txt")


def replace_line(payload: str, field_name: str, replacement: str) -> str:
    lines = payload.splitlines()
    for index, line in enumerate(lines):
        if " ".join(line.split()).startswith(f"{field_name} :"):
            lines[index] = replacement
            return "\n".join(lines)
    raise AssertionError(f"fixture field not found: {field_name}")


def remove_line(payload: str, field_name: str) -> str:
    return "\n".join(
        line
        for line in payload.splitlines()
        if not " ".join(line.split()).startswith(f"{field_name} :")
    )


def test_parses_every_documented_indexed_field() -> None:
    payload = indexed_payload()

    result = parse_info(payload, RECEIVED_AT, expected_position=2)

    assert result.received_at == datetime(
        2026,
        7,
        17,
        1,
        20,
        57,
        tzinfo=timezone.utc,
    )
    assert result.received_at.tzinfo is timezone.utc
    assert result.position == 2
    assert result.barcode == "HPTCR03170C09377"
    assert result.manufacturer == "Pylon"
    assert result.device_name == "US2000C"
    assert result.board_version == "V10R04"
    assert result.main_software_version == "B67.5.0"
    assert result.software_version == "V1.7"
    assert result.boot_version == "V2.0"
    assert result.communication_version == "V2.0"
    assert result.release_date_raw == "20-12-11"
    assert result.specification == "48V/50AH"
    assert result.cell_count == 15
    assert result.max_discharge_current_ma == -90000
    assert result.max_charge_current_ma == 90000
    assert result.epon_port_rate == 1200
    assert result.console_port_rate == 115200
    assert dict(result.extra_fields) == {}
    assert result.raw_payload == payload


def test_parses_local_anonymized_capture() -> None:
    result = parse_info(capture_payload("info.txt"), RECEIVED_AT)

    assert result.position == 1
    assert result.barcode == "<REDACTED>"


def test_accepts_whitespace_variants() -> None:
    payload = indexed_payload().replace(
        "Manufacturer        : Pylon",
        "  Manufacturer\t:\t Pylon  ",
    )

    result = parse_info(payload, RECEIVED_AT, expected_position=2)

    assert result.manufacturer == "Pylon"
    assert result.software_version == "V1.7"


def test_rejects_naive_received_at() -> None:
    with pytest.raises(InfoParserError, match="timezone-aware"):
        parse_info(indexed_payload(), datetime(2026, 7, 17))


@pytest.mark.parametrize(
    "payload",
    [
        indexed_payload().replace("\nCommand completed successfully", ""),
        indexed_payload().replace(
            "Command completed successfully",
            "Command completed successful",
        ),
        (
            "Command completed successfully\n"
            f"{indexed_payload()}"
        ),
        f"{indexed_payload()}\nunexpected",
    ],
)
def test_rejects_invalid_success_confirmation(payload: str) -> None:
    with pytest.raises(InfoParserError, match="success|final non-empty"):
        parse_info(payload, RECEIVED_AT)


def test_accepts_matching_indexed_position() -> None:
    assert parse_info(indexed_payload(), RECEIVED_AT, 2).position == 2


def test_rejects_mismatching_indexed_position() -> None:
    with pytest.raises(InfoParserError, match="does not match"):
        parse_info(indexed_payload(), RECEIVED_AT, 3)


@pytest.mark.parametrize("position", [0, 17])
def test_rejects_out_of_range_expected_position(position: int) -> None:
    with pytest.raises(InfoParserError, match="expected_position outside"):
        parse_info(indexed_payload(), RECEIVED_AT, position)


@pytest.mark.parametrize("position", ["0", "17"])
def test_rejects_out_of_range_returned_position(position: str) -> None:
    payload = replace_line(
        indexed_payload(),
        "Device address",
        f"Device address : {position}",
    )

    with pytest.raises(InfoParserError, match="Device address outside"):
        parse_info(payload, RECEIVED_AT)


@pytest.mark.parametrize("barcode", ["", "   "])
def test_rejects_empty_barcode(barcode: str) -> None:
    payload = replace_line(
        indexed_payload(),
        "Barcode",
        f"Barcode : {barcode}",
    )

    with pytest.raises(InfoParserError, match="Barcode"):
        parse_info(payload, RECEIVED_AT)


def test_rejects_missing_required_field() -> None:
    payload = remove_line(indexed_payload(), "Board version")

    with pytest.raises(InfoParserError, match="Board version"):
        parse_info(payload, RECEIVED_AT)


def test_rejects_duplicate_known_field() -> None:
    payload = indexed_payload().replace(
        "Manufacturer        : Pylon",
        "Manufacturer        : Pylon\nManufacturer : Other",
    )

    with pytest.raises(InfoParserError, match="duplicate"):
        parse_info(payload, RECEIVED_AT)


@pytest.mark.parametrize(
    ("field_name", "replacement", "message"),
    [
        ("Cell Number", "Cell Number : fifteen", "Cell Number"),
        ("EPONPort rate", "EPONPort rate : fast", "EPONPort rate"),
        ("Console Port rate", "Console Port rate : fast", "Console Port rate"),
        ("Device address", "Device address : two", "Device address"),
        ("Max Dischg Curr", "Max Dischg Curr : -90000", "mA"),
        ("Max Charge Curr", "Max Charge Curr : mA", "Max Charge Curr"),
    ],
)
def test_rejects_malformed_numeric_fields(
    field_name: str,
    replacement: str,
    message: str,
) -> None:
    payload = replace_line(indexed_payload(), field_name, replacement)

    with pytest.raises(InfoParserError, match=message):
        parse_info(payload, RECEIVED_AT)


def test_rejects_malformed_key_value_line() -> None:
    payload = indexed_payload().replace(
        "Manufacturer        : Pylon",
        "Manufacturer Pylon",
    )

    with pytest.raises(InfoParserError, match="no colon"):
        parse_info(payload, RECEIVED_AT)


def test_rejects_missing_records() -> None:
    with pytest.raises(InfoParserError, match="no key/value"):
        parse_info("Command completed successfully", RECEIVED_AT)


def test_preserves_unknown_fields_in_response_order() -> None:
    payload = indexed_payload().replace(
        "Command completed successfully",
        "Unknown A : raw value\nUnknown B : second: value\n"
        "Command completed successfully",
    )

    result = parse_info(payload, RECEIVED_AT)

    assert list(result.extra_fields.items()) == [
        ("Unknown A", "raw value"),
        ("Unknown B", "second: value"),
    ]
