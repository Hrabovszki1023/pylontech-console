from datetime import UTC, datetime
from typing import cast

import pytest

from pylontech_console.console_session import (
    AuthenticatedConsoleClient,
    ConsoleAuthenticationError,
    ConsoleSessionHealthStore,
    ConsoleSessionMode,
)
from pylontech_console.framing.console import ConsoleExchange, FramedConsoleClient
from pylontech_console.transport.tcp import AsyncTcpTransport

NOW = datetime(2026, 7, 28, 6, 0, tzinfo=UTC)


def exchange(
    payload: str,
    mode: ConsoleSessionMode,
    *,
    succeeded: bool,
) -> ConsoleExchange:
    return ConsoleExchange(
        payload=payload,
        prompt="pylon_debug>" if mode is ConsoleSessionMode.DEBUG else "pylon>",
        mode=mode,
        succeeded=succeeded,
    )


class FakeTransport:
    is_connected = True
    connection_generation = 1

    async def ensure_connected(self) -> None:
        self.is_connected = True


class FakeConsole:
    def __init__(self, responses: list[ConsoleExchange]) -> None:
        self.responses = responses
        self.commands: list[str] = []

    async def exchange(self, command: str) -> ConsoleExchange:
        self.commands.append(command)
        return self.responses.pop(0)


def client(
    transport: FakeTransport,
    console: FakeConsole,
    health: ConsoleSessionHealthStore,
) -> AuthenticatedConsoleClient:
    return AuthenticatedConsoleClient(
        cast(AsyncTcpTransport, transport),
        cast(FramedConsoleClient, console),
        "configured-secret",
        health,
        clock=lambda: NOW,
    )


@pytest.mark.asyncio
async def test_already_debug_session_does_not_repeat_login() -> None:
    transport = FakeTransport()
    console = FakeConsole(
        [
            exchange(
                "rack\nCommand completed successfully",
                ConsoleSessionMode.DEBUG,
                succeeded=True,
            ),
            exchange(
                "topology\nCommand completed successfully",
                ConsoleSessionMode.DEBUG,
                succeeded=True,
            ),
        ],
    )
    health = ConsoleSessionHealthStore()
    authenticated = client(transport, console, health)

    await authenticated.establish()
    assert await authenticated.execute("pwr") == (
        "topology\nCommand completed successfully"
    )

    assert console.commands == ["pwrsys", "pwr"]
    assert health.get().authenticated
    assert health.get().last_authenticated_at == NOW


@pytest.mark.asyncio
async def test_user_mode_logs_in_before_polling() -> None:
    console = FakeConsole(
        [
            exchange(
                "Unknown command 'pwrsys' - try 'help'",
                ConsoleSessionMode.USER,
                succeeded=False,
            ),
            exchange(
                "Command completed successfully",
                ConsoleSessionMode.DEBUG,
                succeeded=True,
            ),
            exchange(
                "topology\nCommand completed successfully",
                ConsoleSessionMode.DEBUG,
                succeeded=True,
            ),
        ],
    )
    health = ConsoleSessionHealthStore()
    authenticated = client(FakeTransport(), console, health)

    await authenticated.establish()
    await authenticated.execute("pwr")

    assert console.commands == [
        "pwrsys",
        "login configured-secret",
        "pwr",
    ]
    assert health.get().mode is ConsoleSessionMode.DEBUG


@pytest.mark.asyncio
async def test_rejected_password_fails_closed_without_polling() -> None:
    console = FakeConsole(
        [
            exchange(
                "Unknown command 'pwrsys' - try 'help'",
                ConsoleSessionMode.USER,
                succeeded=False,
            ),
            exchange(
                "Invalid command or fail to excute.",
                ConsoleSessionMode.USER,
                succeeded=False,
            ),
        ],
    )
    health = ConsoleSessionHealthStore()
    authenticated = client(FakeTransport(), console, health)

    with pytest.raises(ConsoleAuthenticationError):
        await authenticated.establish()

    assert console.commands == ["pwrsys", "login configured-secret"]
    assert not health.get().authenticated
    assert health.get().mode is ConsoleSessionMode.USER
    assert health.get().error == "console authentication failed"
    assert "configured-secret" not in repr(health.get())


@pytest.mark.asyncio
async def test_new_transport_generation_reauthenticates_before_command() -> None:
    transport = FakeTransport()
    console = FakeConsole(
        [
            exchange(
                "rack\nCommand completed successfully",
                ConsoleSessionMode.DEBUG,
                succeeded=True,
            ),
            exchange(
                "one\nCommand completed successfully",
                ConsoleSessionMode.DEBUG,
                succeeded=True,
            ),
            exchange(
                "rack\nCommand completed successfully",
                ConsoleSessionMode.DEBUG,
                succeeded=True,
            ),
            exchange(
                "two\nCommand completed successfully",
                ConsoleSessionMode.DEBUG,
                succeeded=True,
            ),
        ],
    )
    authenticated = client(
        transport,
        console,
        ConsoleSessionHealthStore(),
    )

    await authenticated.establish()
    await authenticated.execute("pwr")
    transport.connection_generation = 2
    await authenticated.execute("info 1")

    assert console.commands == ["pwrsys", "pwr", "pwrsys", "info 1"]


@pytest.mark.asyncio
async def test_command_returning_user_prompt_fails_closed() -> None:
    console = FakeConsole(
        [
            exchange(
                "rack\nCommand completed successfully",
                ConsoleSessionMode.DEBUG,
                succeeded=True,
            ),
            exchange(
                "Unknown command 'pwr' - try 'help'",
                ConsoleSessionMode.USER,
                succeeded=False,
            ),
        ],
    )
    health = ConsoleSessionHealthStore()
    authenticated = client(FakeTransport(), console, health)

    await authenticated.establish()
    with pytest.raises(
        ConsoleAuthenticationError,
        match="console session left debug mode",
    ):
        await authenticated.execute("pwr")

    assert not health.get().authenticated
    assert health.get().mode is ConsoleSessionMode.USER
    assert health.get().error == "console session left debug mode"


@pytest.mark.asyncio
async def test_controlled_logout_requires_user_prompt() -> None:
    console = FakeConsole(
        [
            exchange(
                "rack\nCommand completed successfully",
                ConsoleSessionMode.DEBUG,
                succeeded=True,
            ),
            exchange(
                "Command completed successfully",
                ConsoleSessionMode.USER,
                succeeded=True,
            ),
        ],
    )
    health = ConsoleSessionHealthStore()
    authenticated = client(FakeTransport(), console, health)

    await authenticated.establish()
    await authenticated.logout()

    assert console.commands == ["pwrsys", "logout"]
    assert health.get().mode is ConsoleSessionMode.USER
    assert not health.get().authenticated
