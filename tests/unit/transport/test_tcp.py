import asyncio
from typing import Any

import pytest

from pylontech_console.transport.tcp import AsyncTcpTransport


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


@pytest.mark.asyncio
async def test_connect_uses_configured_target_and_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, int]] = []
    writer = FakeWriter()

    async def fake_open_connection(host: str, port: int) -> tuple[Any, Any]:
        calls.append((host, port))
        return asyncio.StreamReader(), writer

    monkeypatch.setattr(asyncio, "open_connection", fake_open_connection)
    transport = AsyncTcpTransport("gateway.local", 4196, 5)

    await transport.connect()
    await transport.connect()

    assert calls == [("gateway.local", 4196)]
    assert transport.is_connected

    await transport.disconnect()

    assert writer.closed
    assert writer.waited_closed
    assert not transport.is_connected


@pytest.mark.asyncio
async def test_disconnect_is_idempotent() -> None:
    transport = AsyncTcpTransport("gateway.local", 4196, 5)

    await transport.disconnect()
    await transport.disconnect()

    assert not transport.is_connected


@pytest.mark.asyncio
async def test_connection_failure_leaves_transport_disconnected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def refuse_connection(host: str, port: int) -> tuple[Any, Any]:
        raise OSError(f"refused {host}:{port}")

    monkeypatch.setattr(asyncio, "open_connection", refuse_connection)
    transport = AsyncTcpTransport("gateway.local", 4196, 5)

    with pytest.raises(OSError, match="refused gateway.local:4196"):
        await transport.connect()

    assert not transport.is_connected


@pytest.mark.asyncio
async def test_connect_timeout_leaves_transport_disconnected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocker = asyncio.Event()

    async def blocked_connection(
        host: str,
        port: int,
    ) -> tuple[Any, Any]:
        await blocker.wait()
        raise AssertionError(f"unexpected connection to {host}:{port}")

    monkeypatch.setattr(asyncio, "open_connection", blocked_connection)
    transport = AsyncTcpTransport("gateway.local", 4196, 0.01)

    with pytest.raises(TimeoutError):
        await transport.connect()

    assert not transport.is_connected


@pytest.mark.asyncio
async def test_failed_exchange_reconnects_with_bounded_backoff(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls = 0
    writers: list[FakeWriter] = []
    delays: list[float] = []

    async def fake_open_connection(host: str, port: int) -> tuple[Any, Any]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ConnectionRefusedError(f"refused {host}:{port}")
        writer = FakeWriter()
        writers.append(writer)
        return asyncio.StreamReader(), writer

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    async def fail_read(reader: asyncio.StreamReader) -> str:
        raise ConnectionResetError("peer reset")

    async def successful_read(reader: asyncio.StreamReader) -> str:
        return "recovered"

    monkeypatch.setattr(asyncio, "open_connection", fake_open_connection)
    transport = AsyncTcpTransport(
        "gateway.local",
        4196,
        5,
        reconnect_min_seconds=1,
        reconnect_max_seconds=2,
        sleep=fake_sleep,
    )
    await transport.connect()

    with pytest.raises(ConnectionResetError, match="peer reset"):
        await transport.exchange(b"first", fail_read, 1)

    assert not transport.is_connected
    assert writers[0].closed

    with pytest.raises(ConnectionRefusedError, match="refused"):
        await transport.exchange(b"second", successful_read, 1)

    assert not transport.is_connected
    assert delays == [1]

    result = await transport.exchange(b"third", successful_read, 1)

    assert result == "recovered"
    assert transport.is_connected
    assert delays == [1, 2]
    assert calls == 3
    assert writers[1].written == b"third"
    assert "Waveshare TCP reconnect scheduled in 1.0 seconds" in caplog.text
    assert "Waveshare TCP reconnect failed" in caplog.text
    assert "Waveshare TCP reconnect scheduled in 2.0 seconds" in caplog.text
    assert "Waveshare TCP reconnect succeeded" in caplog.text


@pytest.mark.parametrize(
    ("minimum", "maximum", "message"),
    [
        (0, 1, "minimum must be greater than zero"),
        (2, 1, "maximum must not be below minimum"),
    ],
)
def test_rejects_invalid_reconnect_bounds(
    minimum: float,
    maximum: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        AsyncTcpTransport(
            "gateway.local",
            4196,
            5,
            reconnect_min_seconds=minimum,
            reconnect_max_seconds=maximum,
        )


def test_transport_module_uses_only_standard_library_dependencies() -> None:
    import ast
    import inspect

    from pylontech_console.transport import tcp

    tree = ast.parse(inspect.getsource(tcp))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert imports == {"asyncio", "logging"}
