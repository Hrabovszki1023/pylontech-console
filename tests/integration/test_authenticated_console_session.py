import asyncio
from collections.abc import Awaitable, Callable

import pytest

from pylontech_console.console_session import (
    AuthenticatedConsoleClient,
    ConsoleSessionHealthStore,
    ConsoleSessionMode,
)
from pylontech_console.framing.console import FramedConsoleClient
from pylontech_console.transport.tcp import AsyncTcpTransport

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
async def test_login_poll_and_logout_against_controlled_console() -> None:
    commands: list[str] = []

    async def handle(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        responses = (
            (
                "pwrsys",
                "Unknown command 'pwrsys' - try 'help'",
                "pylon>",
            ),
            (
                "login configured-secret",
                "Command completed successfully",
                "pylon_debug>",
            ),
            (
                "pwr",
                "rack data\r\nCommand completed successfully",
                "pylon_debug>",
            ),
            (
                "logout",
                "Command completed successfully",
                "pylon>",
            ),
        )
        for expected, payload, prompt in responses:
            command = (await reader.readuntil(b"\r")).decode("ascii").rstrip("\r")
            commands.append(command)
            assert command == expected
            writer.write(
                f"{command}\r\n@\r\n{payload}\r\n$${prompt}".encode("ascii"),
            )
            await writer.drain()

    server, port = await start_server(handle)
    transport = AsyncTcpTransport("127.0.0.1", port, 1)
    console = FramedConsoleClient(transport, 1)
    health = ConsoleSessionHealthStore()
    client = AuthenticatedConsoleClient(
        transport,
        console,
        "configured-secret",
        health,
    )

    try:
        await transport.connect()
        await client.establish()
        assert await client.execute("pwr") == (
            "rack data\r\nCommand completed successfully"
        )
        await client.logout()

        assert commands == [
            "pwrsys",
            "login configured-secret",
            "pwr",
            "logout",
        ]
        assert health.get().mode is ConsoleSessionMode.USER
        assert not health.get().authenticated
    finally:
        await transport.disconnect()
        server.close()
        await server.wait_closed()
