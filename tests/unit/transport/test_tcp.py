import asyncio
from typing import Any

import pytest

from pylontech_console.transport.tcp import AsyncTcpTransport


class FakeWriter:
    def __init__(self) -> None:
        self.closed = False
        self.waited_closed = False

    def is_closing(self) -> bool:
        return self.closed

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        self.waited_closed = True


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

    assert imports == {"asyncio"}
