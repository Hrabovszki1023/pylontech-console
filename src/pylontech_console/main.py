import asyncio
from dataclasses import replace

import uvicorn
from fastapi import FastAPI

from pylontech_console.commands import ReadOnlyPylontechClient
from pylontech_console.config import (
    load_http_settings,
    load_mqtt_settings,
    load_polling_settings,
    load_waveshare_settings,
    load_web_settings,
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


class ServiceRuntime:
    def __init__(
        self,
        transport: AsyncTcpTransport,
        polling: PollingService,
        mqtt: MqttPublisher,
    ) -> None:
        self._transport = transport
        self._polling = polling
        self._mqtt = mqtt
        self._unsubscribe = polling.store.subscribe(mqtt.notify_state)

    async def start(self) -> None:
        await self._mqtt.start()
        try:
            await self._transport.connect()
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
        await self._transport.disconnect()


def build_production_application() -> tuple[FastAPI, str, int]:
    waveshare = load_waveshare_settings()
    polling_settings = load_polling_settings()
    http = load_http_settings()
    web = load_web_settings()
    mqtt_settings = load_mqtt_settings()
    transport = AsyncTcpTransport(
        waveshare.host,
        waveshare.port,
        waveshare.connect_timeout_seconds,
    )
    console = FramedConsoleClient(
        transport,
        waveshare.response_timeout_seconds,
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
    query = StateQuery(polling.store, mqtt_health=mqtt_health)
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
    runtime = ServiceRuntime(transport, polling, mqtt)
    app = create_application(
        polling.store,
        query=query,
        runtime=runtime,
    )
    mount_web(app, query, web)
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
