import asyncio

import pytest

from pylontech_console.transport.tcp import AsyncTcpTransport


@pytest.mark.asyncio
async def test_connects_to_controlled_tcp_server_and_disconnects() -> None:
    accepted_connections = 0
    peer_closed = asyncio.Event()

    async def handle_connection(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        nonlocal accepted_connections
        accepted_connections += 1
        try:
            await reader.read()
        finally:
            writer.close()
            await writer.wait_closed()
            peer_closed.set()

    server = await asyncio.start_server(handle_connection, "127.0.0.1", 0)
    sockets = server.sockets
    assert sockets
    port = int(sockets[0].getsockname()[1])
    transport = AsyncTcpTransport("127.0.0.1", port, 1)

    try:
        assert not transport.is_connected

        await transport.connect()

        assert transport.is_connected
        assert accepted_connections == 1

        await transport.disconnect()
        await asyncio.wait_for(peer_closed.wait(), timeout=1)

        assert not transport.is_connected
    finally:
        await transport.disconnect()
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_connection_refusal_from_closed_local_port() -> None:
    server = await asyncio.start_server(
        lambda reader, writer: None,
        "127.0.0.1",
        0,
    )
    sockets = server.sockets
    assert sockets
    port = int(sockets[0].getsockname()[1])
    server.close()
    await server.wait_closed()
    transport = AsyncTcpTransport("127.0.0.1", port, 1)

    with pytest.raises(OSError):
        await transport.connect()

    assert not transport.is_connected
