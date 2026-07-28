import asyncio

import pytest

from pylontech_console.framing.console import (
    MAX_EXCHANGE_BYTES,
    CommandEncodingError,
    IncompleteResponseError,
    ResponseEncodingError,
    ResponseTooLargeError,
    encode_command,
    read_console_exchange,
    read_framed_ascii_payload,
)


def reader_with(data: bytes, *, eof: bool = True) -> asyncio.StreamReader:
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    if eof:
        reader.feed_eof()
    return reader


def test_encode_command_appends_exact_carriage_return() -> None:
    assert encode_command("pwr") == b"pwr\r"


def test_encode_command_rejects_non_ascii() -> None:
    with pytest.raises(CommandEncodingError):
        encode_command("pwör")


@pytest.mark.asyncio
async def test_extracts_payload_and_ignores_echo_and_prompt() -> None:
    reader = reader_with(
        b"pylon_debug>pwr\r\n@\r\nfirst\r\nsecond\r\n"
        b"Command completed successfully\r\n$$pylon_debug>",
    )

    payload = await read_framed_ascii_payload(reader)

    assert payload == "first\r\nsecond\r\nCommand completed successfully"


@pytest.mark.asyncio
async def test_removes_only_adjacent_marker_line_endings() -> None:
    reader = reader_with(b"@\n\npayload\n\n$$")

    payload = await read_framed_ascii_payload(reader)

    assert payload == "\npayload\n"


@pytest.mark.asyncio
async def test_supports_markers_split_across_chunks() -> None:
    reader = asyncio.StreamReader()

    async def feed_chunks() -> None:
        for chunk in (b"echo\r\n", b"@", b"\r", b"\npayload\r\n$", b"$"):
            reader.feed_data(chunk)
            await asyncio.sleep(0)

    feeder = asyncio.create_task(feed_chunks())
    payload = await read_framed_ascii_payload(reader)
    await feeder

    assert payload == "payload"


@pytest.mark.asyncio
async def test_rejects_non_ascii_response() -> None:
    reader = reader_with(b"@\r\ninvalid:\xff\r\n$$")

    with pytest.raises(ResponseEncodingError):
        await read_framed_ascii_payload(reader)


@pytest.mark.asyncio
async def test_rejects_eof_before_end_marker() -> None:
    reader = reader_with(b"@\r\npartial")

    with pytest.raises(IncompleteResponseError):
        await read_framed_ascii_payload(reader)


@pytest.mark.asyncio
async def test_accepts_exact_exchange_size_limit() -> None:
    payload = b"x" * (MAX_EXCHANGE_BYTES - len(b"@$$"))
    reader = reader_with(b"@" + payload + b"$$")

    result = await read_framed_ascii_payload(reader)

    assert result == payload.decode("ascii")


@pytest.mark.asyncio
async def test_rejects_exchange_above_size_limit() -> None:
    payload = b"x" * (MAX_EXCHANGE_BYTES - len(b"@$$") + 1)
    reader = reader_with(b"@" + payload + b"$$")

    with pytest.raises(ResponseTooLargeError):
        await read_framed_ascii_payload(reader)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("prompt", "expected_mode"),
    [
        (b"pylon>", "user"),
        (b"pylon_debug>", "debug"),
    ],
)
async def test_parses_prompt_separately_from_framed_payload(
    prompt: bytes,
    expected_mode: str,
) -> None:
    reader = reader_with(
        b"echo\r\n@\r\nCommand completed successfully\r\n$$\r\n" + prompt,
    )

    result = await read_console_exchange(reader)

    assert result.payload == "Command completed successfully"
    assert result.prompt == prompt.decode("ascii")
    assert result.mode.value == expected_mode
    assert result.succeeded


@pytest.mark.asyncio
async def test_valid_command_rejection_is_a_complete_user_exchange() -> None:
    reader = reader_with(
        b"@\r\nUnknown command 'pwrsys' - try 'help'\r\n$$\r\npylon>",
    )

    result = await read_console_exchange(reader)

    assert result.mode.value == "user"
    assert not result.succeeded
    assert "Unknown command" in result.payload


@pytest.mark.asyncio
async def test_at_sign_in_command_echo_is_not_the_response_marker() -> None:
    reader = reader_with(
        b"login p@ssword\r\n@\r\nCommand completed successfully\r\n"
        b"$$pylon_debug>",
    )

    result = await read_console_exchange(reader)

    assert result.succeeded
    assert result.mode.value == "debug"


@pytest.mark.asyncio
async def test_rejects_eof_before_following_prompt() -> None:
    reader = reader_with(b"@\r\nCommand completed successfully\r\n$$")

    with pytest.raises(IncompleteResponseError):
        await read_console_exchange(reader)
