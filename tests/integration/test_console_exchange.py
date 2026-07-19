import asyncio
from collections.abc import Awaitable, Callable

import pytest

from pylontech_console.framing.console import (
    FramedConsoleClient,
    IncompleteResponseError,
    ResponseEncodingError,
    ResponseTooLargeError,
)
from pylontech_console.transport.tcp import (
    AsyncTcpTransport,
    TransportNotConnectedError,
    TransportResponseTimeoutError,
)

ServerHandler = Callable[
    [asyncio.StreamReader, asyncio.StreamWriter],
    Awaitable[None],
]


async def start_server(
    handler: ServerHandler,
) -> tuple[asyncio.AbstractServer, int]:
    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    sockets = server.sockets
    assert sockets
    return server, int(sockets[0].getsockname()[1])


@pytest.mark.asyncio
async def test_exchange_with_fragmented_controlled_server() -> None:
    received = bytearray()

    async def handle(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        received.extend(await reader.readuntil(b"\r"))
        for chunk in (
            b"pylon_debug>pwr\r\n",
            b"@",
            b"\r\npayload\r\n",
            b"Command completed successfully\r\n$",
            b"$pylon_debug>",
        ):
            writer.write(chunk)
            await writer.drain()
            await asyncio.sleep(0)

    server, port = await start_server(handle)
    transport = AsyncTcpTransport("127.0.0.1", port, 1)
    client = FramedConsoleClient(transport, 1)

    try:
        await transport.connect()
        payload = await client.execute("pwr")

        assert received == b"pwr\r"
        assert payload == "payload\r\nCommand completed successfully"
        assert transport.is_connected
    finally:
        await transport.disconnect()
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_consecutive_exchanges_ignore_previous_prompt() -> None:
    commands: list[bytes] = []

    async def handle(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        for response in (b"one", b"two"):
            commands.append(await reader.readuntil(b"\r"))
            writer.write(
                commands[-1] + b"\n@\n" + response + b"\n$$pylon_debug>",
            )
            await writer.drain()

    server, port = await start_server(handle)
    transport = AsyncTcpTransport("127.0.0.1", port, 1)
    client = FramedConsoleClient(transport, 1)

    try:
        await transport.connect()

        assert await client.execute("pwr") == "one"
        assert await client.execute("info 1") == "two"
        assert commands == [b"pwr\r", b"info 1\r"]
    finally:
        await transport.disconnect()
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_serializes_concurrent_exchanges() -> None:
    first_response_sent = asyncio.Event()
    second_command_before_first_response = False

    async def handle(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        nonlocal second_command_before_first_response
        first = await reader.readuntil(b"\r")
        assert first == b"first\r"
        try:
            await asyncio.wait_for(reader.readuntil(b"\r"), timeout=0.02)
            second_command_before_first_response = True
        except TimeoutError:
            pass
        writer.write(b"@\nfirst response\n$$")
        await writer.drain()
        first_response_sent.set()
        second = await reader.readuntil(b"\r")
        assert second == b"second\r"
        writer.write(b"@\nsecond response\n$$")
        await writer.drain()

    server, port = await start_server(handle)
    transport = AsyncTcpTransport("127.0.0.1", port, 1)
    client = FramedConsoleClient(transport, 1)

    try:
        await transport.connect()
        first_task = asyncio.create_task(client.execute("first"))
        second_task = asyncio.create_task(client.execute("second"))

        assert await first_task == "first response"
        await first_response_sent.wait()
        assert await second_task == "second response"
        assert not second_command_before_first_response
    finally:
        await transport.disconnect()
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_requires_connected_transport() -> None:
    transport = AsyncTcpTransport("127.0.0.1", 4196, 1)
    client = FramedConsoleClient(transport, 1)

    with pytest.raises(TransportNotConnectedError):
        await client.execute("pwr")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "expected_error"),
    [
        (b"@\npartial", IncompleteResponseError),
        (b"@\ninvalid:\xff\n$$", ResponseEncodingError),
        (b"@" + b"x" * 16_382 + b"$$", ResponseTooLargeError),
    ],
)
async def test_protocol_failure_disconnects_transport(
    response: bytes,
    expected_error: type[Exception],
) -> None:
    async def handle(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        await reader.readuntil(b"\r")
        writer.write(response)
        await writer.drain()
        if expected_error is IncompleteResponseError:
            writer.close()

    server, port = await start_server(handle)
    transport = AsyncTcpTransport("127.0.0.1", port, 1)
    client = FramedConsoleClient(transport, 1)

    try:
        await transport.connect()

        with pytest.raises(expected_error):
            await client.execute("pwr")

        assert not transport.is_connected
    finally:
        await transport.disconnect()
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_response_timeout_disconnects_transport() -> None:
    blocker = asyncio.Event()

    async def handle(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        await reader.readuntil(b"\r")
        await blocker.wait()

    server, port = await start_server(handle)
    transport = AsyncTcpTransport("127.0.0.1", port, 1)
    client = FramedConsoleClient(transport, 0.01)

    try:
        await transport.connect()

        with pytest.raises(TransportResponseTimeoutError):
            await client.execute("pwr")

        assert not transport.is_connected
    finally:
        blocker.set()
        await transport.disconnect()
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_peer_abort_before_end_marker_disconnects_transport() -> None:
    peer_aborted = asyncio.Event()

    async def handle(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        await reader.readuntil(b"\r")
        writer.write(b"@\npartial")
        await writer.drain()
        writer.transport.abort()
        peer_aborted.set()

    server, port = await start_server(handle)
    transport = AsyncTcpTransport("127.0.0.1", port, 1)
    client = FramedConsoleClient(transport, 1)

    try:
        await transport.connect()

        with pytest.raises((IncompleteResponseError, ConnectionResetError)):
            await client.execute("pwr")

        await peer_aborted.wait()
        assert not transport.is_connected
    finally:
        await transport.disconnect()
        server.close()
        await server.wait_closed()
