import logging
from typing import cast

import pytest

from pylontech_console.console_session import AuthenticatedConsoleClient
from pylontech_console.domain.current_state import CurrentState
from pylontech_console.main import ServiceRuntime
from pylontech_console.outputs.mqtt import MqttPublisher
from pylontech_console.polling import CurrentStateStore, PollingService
from pylontech_console.transport.tcp import AsyncTcpTransport
from pylontech_console.version import BuildIdentity

REVISION = "fc830cd8ff0e2ebcde20094a91709a87ef8b713b"


class FakeTransport:
    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass


class FakeConsole:
    async def establish(self) -> None:
        pass

    async def logout(self) -> None:
        pass


class FakePolling:
    def __init__(self) -> None:
        self.store = CurrentStateStore(CurrentState.empty(5, 60, 300, 2))

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass


class FakeMqtt:
    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    def notify_state(self, _state: CurrentState) -> None:
        pass


@pytest.mark.asyncio
async def test_runtime_logs_exact_build_identity_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    identity = BuildIdentity(
        name="pylontech-console",
        display_name="Pylontech Console",
        version="0.1.0-beta.1",
        revision=REVISION,
    )
    runtime = ServiceRuntime(
        cast(AsyncTcpTransport, FakeTransport()),
        cast(AuthenticatedConsoleClient, FakeConsole()),
        cast(PollingService, FakePolling()),
        cast(MqttPublisher, FakeMqtt()),
        identity,
    )

    with caplog.at_level(logging.INFO, logger="pylontech_console.main"):
        await runtime.start()
        await runtime.stop()

    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "pylontech_console.main"
    ]
    assert messages == [
        "starting pylontech-console "
        f"version=0.1.0-beta.1 revision={REVISION}",
    ]
