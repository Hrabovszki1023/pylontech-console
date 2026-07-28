import asyncio
import logging
from dataclasses import replace

import uvicorn
from fastapi import FastAPI

from pylontech_console.commands import ReadOnlyPylontechClient
from pylontech_console.config import (
    load_console_settings,
    load_http_settings,
    load_mqtt_settings,
    load_polling_settings,
    load_waveshare_settings,
    load_web_settings,
)
from pylontech_console.console_session import (
    AuthenticatedConsoleClient,
    ConsoleSessionHealthStore,
)
from pylontech_console.domain.current_state import ConnectionState
from pylontech_console.framing.console import FramedConsoleClient
from pylontech_console.mqtt_health import MqttHealth, MqttHealthStore
from pylontech_console.outputs.api import create_application
from pylontech_console.outputs.api.query import StateQuery
from pylontech_console.outputs.mqtt import MqttPublisher, SnapshotSerializer
from pylontech_console.outputs.web import mount_web
from pylontech_console.polling import PollingService, utc_now
from pylontech_console.transport.tcp import AsyncTcpTransport
from pylontech_console.version import BuildIdentity, load_build_identity

LOGGER = logging.getLogger(__name__)


class ServiceRuntime:
    def __init__(
        self,
        transport: AsyncTcpTransport,
        console: AuthenticatedConsoleClient,
        polling: PollingService,
        mqtt: MqttPublisher,
        identity: BuildIdentity,
    ) -> None:
        self._transport = transport
        self._console = console
        self._polling = polling
        self._mqtt = mqtt
        self._identity = identity
        self._unsubscribe = polling.store.subscribe(mqtt.notify_state)

    async def start(self) -> None:
        LOGGER.info(
            "starting %s version=%s revision=%s",
            self._identity.name,
            self._identity.version,
            self._identity.revision,
        )
        await self._mqtt.start()
        try:
            await self._transport.connect()
            await self._console.establish()
            await self._polling.start()
        except (OSError, RuntimeError, TimeoutError, ValueError):
            state = self._polling.store.get()
            self._polling.store.publish(
                replace(
                    state,
                    connection=ConnectionState.OFFLINE,
                    updated_at=utc_now(),
                    consecutive_failures=state.consecutive_failures + 1,
                ),
            )

    async def stop(self) -> None:
        self._unsubscribe()
        await self._mqtt.stop()
        await self._polling.stop()
        await self._console.logout()
        await self._transport.disconnect()


def build_production_application() -> tuple[FastAPI, str, int]:
    identity = load_build_identity()
    waveshare = load_waveshare_settings()
    console_settings = load_console_settings()
    polling_settings = load_polling_settings()
    http = load_http_settings()
    web = load_web_settings()
    mqtt_settings = load_mqtt_settings()
    transport = AsyncTcpTransport(
        waveshare.host,
        waveshare.port,
        waveshare.connect_timeout_seconds,
    )
    framed_console = FramedConsoleClient(
        transport,
        waveshare.response_timeout_seconds,
    )
    console_health = ConsoleSessionHealthStore()
    console = AuthenticatedConsoleClient(
        transport,
        framed_console,
        console_settings.password(),
        console_health,
    )
    polling = PollingService(
        ReadOnlyPylontechClient(console),
        polling_settings,
    )
    mqtt_health = MqttHealthStore(
        MqttHealth.connecting()
        if mqtt_settings.enabled
        else MqttHealth.disabled(),
    )
    query = StateQuery(
        polling.store,
        mqtt_health=mqtt_health,
        console_health=console_health,
    )
    mqtt = MqttPublisher(
        mqtt_settings,
        SnapshotSerializer(
            query,
            mqtt_health,
            mqtt_settings.topic_prefix,
        ),
        mqtt_health,
        polling_settings.rack_interval_seconds,
    )
    runtime = ServiceRuntime(transport, console, polling, mqtt, identity)
    app = create_application(
        polling.store,
        query=query,
        runtime=runtime,
        identity=identity,
    )
    mount_web(app, query, web, identity)
    return app, http.host, http.port


async def run() -> None:
    app, host, port = build_production_application()
    server = uvicorn.Server(
        uvicorn.Config(app, host=host, port=port, log_level="info"),
    )
    await server.serve()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
