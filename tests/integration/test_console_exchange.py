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
                commands[-1]
                + b"\n@\n"
                + response
                + b"\nCommand completed successfully\n$$pylon_debug>",
            )
            await writer.drain()

    server, port = await start_server(handle)
    transport = AsyncTcpTransport("127.0.0.1", port, 1)
    client = FramedConsoleClient(transport, 1)

    try:
        await transport.connect()

        assert (
            await client.execute("pwr")
            == "one\nCommand completed successfully"
        )
        assert (
            await client.execute("info 1")
            == "two\nCommand completed successfully"
        )
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
        writer.write(b"@\nfirst response\n$$pylon_debug>")
        await writer.drain()
        first_response_sent.set()
        second = await reader.readuntil(b"\r")
        assert second == b"second\r"
        writer.write(b"@\nsecond response\n$$pylon_debug>")
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
        writer.write(response + b"pylon_debug>")
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


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "eof", "reset"])
async def test_next_exchange_reconnects_after_transport_failure(
    failure: str,
) -> None:
    connections = 0
    commands: list[bytes] = []
    reconnect_delays: list[float] = []
    first_handler_finished = asyncio.Event()

    async def fast_sleep(seconds: float) -> None:
        reconnect_delays.append(seconds)

    async def handle(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        nonlocal connections
        connections += 1
        connection = connections
        command = await reader.readuntil(b"\r")
        commands.append(command)
        if connection == 1:
            if failure == "timeout":
                await reader.read()
            elif failure == "eof":
                writer.close()
                await writer.wait_closed()
            else:
                writer.transport.abort()
            first_handler_finished.set()
            return

        writer.write(
            b"@\nrecovered\nCommand completed successfully\n$$pylon_debug>",
        )
        await writer.drain()

    server, port = await start_server(handle)
    transport = AsyncTcpTransport(
        "127.0.0.1",
        port,
        1,
        reconnect_min_seconds=1,
        reconnect_max_seconds=2,
        sleep=fast_sleep,
    )
    client = FramedConsoleClient(
        transport,
        0.01 if failure == "timeout" else 1,
    )
    recovery_client = FramedConsoleClient(transport, 1)

    try:
        await transport.connect()
        expected_error: tuple[type[BaseException], ...]
        if failure == "timeout":
            expected_error = (TransportResponseTimeoutError,)
        elif failure == "eof":
            expected_error = (IncompleteResponseError,)
        else:
            expected_error = (
                IncompleteResponseError,
                ConnectionResetError,
            )

        with pytest.raises(expected_error):
            await client.execute("first")

        await first_handler_finished.wait()
        assert not transport.is_connected

        assert (
            await recovery_client.execute("second")
            == "recovered\nCommand completed successfully"
        )
        assert transport.is_connected
        assert connections == 2
        assert commands == [b"first\r", b"second\r"]
        assert reconnect_delays == [1]
    finally:
        await transport.disconnect()
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_framed_incomplete_response_reconnects_before_next_command() -> None:
    connections = 0
    commands: list[bytes] = []
    reconnect_delays: list[float] = []
    first_response_release = asyncio.Event()
    six_module_rows = "\r\n".join(
        f"Module {position}: current" for position in range(1, 7)
    ).encode()

    async def fast_sleep(seconds: float) -> None:
        reconnect_delays.append(seconds)

    async def handle(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        nonlocal connections
        connections += 1
        connection_number = connections
        command = await reader.readuntil(b"\r")
        commands.append(command)
        if connection_number == 1:
            writer.write(b"@\r\n" + six_module_rows + b"\r\n$$")
        else:
            writer.write(
                b"@\r\n"
                + six_module_rows
                + b"\r\nCommand completed successfully\r\n$$pylon_debug>",
            )
        await writer.drain()
        if connection_number == 1:
            await first_response_release.wait()

    server, port = await start_server(handle)
    transport = AsyncTcpTransport(
        "127.0.0.1",
        port,
        1,
        reconnect_min_seconds=1,
        reconnect_max_seconds=2,
        sleep=fast_sleep,
    )
    client = FramedConsoleClient(transport, 0.01)
    recovery_client = FramedConsoleClient(transport, 1)

    try:
        await transport.connect()

        with pytest.raises(TransportResponseTimeoutError):
            await client.execute("pwrsys")
        first_response_release.set()

        assert not transport.is_connected
        assert commands == [b"pwrsys\r"]

        payload = await recovery_client.execute("pwrsys")

        assert payload.endswith("Command completed successfully")
        assert payload.count("Module ") == 6
        assert commands == [b"pwrsys\r", b"pwrsys\r"]
        assert connections == 2
        assert reconnect_delays == [1]
    finally:
        first_response_release.set()
        await transport.disconnect()
        server.close()
        await server.wait_closed()
