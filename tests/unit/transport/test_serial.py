import asyncio
from typing import Any

import pytest

from pylontech_console.console_session import (
    AuthenticatedConsoleClient,
    ConsoleSessionHealthStore,
    ConsoleSessionMode,
)
from pylontech_console.framing.console import FramedConsoleClient
from pylontech_console.transport.serial import AsyncSerialTransport
from pylontech_console.transport.tcp import TransportResponseTimeoutError


class FakeWriter:
    def __init__(self) -> None:
        self.closed = False
        self.waited_closed = False
        self.written = bytearray()

    def is_closing(self) -> bool:
        return self.closed

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        self.waited_closed = True

    def write(self, data: bytes) -> None:
        self.written.extend(data)

    async def drain(self) -> None:
        return


class InteractiveWriter(FakeWriter):
    def __init__(self, reader: asyncio.StreamReader) -> None:
        super().__init__()
        self._reader = reader

    def write(self, data: bytes) -> None:
        super().write(data)
        if data == b"pwrsys\r":
            self._reader.feed_data(
                b"pwrsys\r\n@\r\nUnknown command 'pwrsys' - try 'help'\r\n"
                b"$$\r\npylon>",
            )
        elif data == b"login debug\r":
            self._reader.feed_data(
                b"login debug\r\n@\r\nCommand completed successfully\r\n"
                b"$$\r\npylon_debug>",
            )


@pytest.mark.asyncio
async def test_connect_uses_verified_serial_settings() -> None:
    calls: list[dict[str, Any]] = []
    writer = FakeWriter()

    async def opener(**kwargs: Any) -> tuple[Any, Any]:
        calls.append(kwargs)
        return asyncio.StreamReader(), writer

    transport = AsyncSerialTransport(
        "/dev/pylontech-console",
        115200,
        5,
        opener=opener,
    )

    await transport.connect()
    await transport.connect()

    assert calls == [{
        "url": "/dev/pylontech-console",
        "baudrate": 115200,
        "bytesize": 8,
        "parity": "N",
        "stopbits": 1,
        "xonxoff": False,
        "rtscts": False,
        "dsrdtr": False,
    }]
    assert transport.is_connected
    assert transport.connection_generation == 1

    await transport.disconnect()

    assert writer.closed
    assert writer.waited_closed


@pytest.mark.asyncio
async def test_exchange_writes_request_and_returns_response() -> None:
    writer = FakeWriter()

    async def opener(**_kwargs: Any) -> tuple[Any, Any]:
        return asyncio.StreamReader(), writer

    async def read_response(_reader: asyncio.StreamReader) -> str:
        return "response"

    transport = AsyncSerialTransport("/dev/ttyUSB0", 115200, 5, opener=opener)
    await transport.connect()

    result = await transport.exchange(b"pwr\r", read_response, 1)

    assert result == "response"
    assert writer.written == b"pwr\r"


@pytest.mark.asyncio
async def test_timeout_disconnects_and_next_exchange_reconnects() -> None:
    writers: list[FakeWriter] = []
    delays: list[float] = []

    async def opener(**_kwargs: Any) -> tuple[Any, Any]:
        writer = FakeWriter()
        writers.append(writer)
        return asyncio.StreamReader(), writer

    async def sleep(seconds: float) -> None:
        delays.append(seconds)

    async def blocked(_reader: asyncio.StreamReader) -> str:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async def recovered(_reader: asyncio.StreamReader) -> str:
        return "recovered"

    transport = AsyncSerialTransport(
        "/dev/ttyUSB0",
        115200,
        5,
        reconnect_min_seconds=1,
        sleep=sleep,
        opener=opener,
    )
    await transport.connect()

    with pytest.raises(TransportResponseTimeoutError):
        await transport.exchange(b"first", blocked, 0.01)

    assert writers[0].closed
    assert not transport.is_connected

    result = await transport.exchange(b"second", recovered, 1)

    assert result == "recovered"
    assert delays == [1]
    assert len(writers) == 2
    assert writers[1].written == b"second"
    assert transport.connection_generation == 2


@pytest.mark.asyncio
async def test_serial_transport_establishes_authenticated_debug_session() -> None:
    reader = asyncio.StreamReader()
    writer = InteractiveWriter(reader)

    async def opener(**_kwargs: Any) -> tuple[Any, Any]:
        return reader, writer

    transport = AsyncSerialTransport(
        "/dev/pylontech-console",
        115200,
        5,
        opener=opener,
    )
    framed = FramedConsoleClient(transport, 1)
    health = ConsoleSessionHealthStore()
    console = AuthenticatedConsoleClient(
        transport,
        framed,
        "debug",
        health,
    )

    await transport.connect()
    await console.establish()

    assert writer.written == b"pwrsys\rlogin debug\r"
    assert health.get().mode is ConsoleSessionMode.DEBUG
    assert health.get().authenticated is True
