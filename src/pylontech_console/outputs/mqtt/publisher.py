import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol, cast

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from pylontech_console.config import MqttSettings
from pylontech_console.domain.current_state import CurrentState
from pylontech_console.mqtt_health import MqttHealthStore
from pylontech_console.outputs.mqtt.serializer import (
    Publication,
    SnapshotSerializer,
)

LOGGER = logging.getLogger(__name__)


class PublishResult(Protocol):
    rc: int

    def wait_for_publish(self, timeout: float | None = None) -> None: ...


class MqttClient(Protocol):
    on_connect: Any
    on_connect_fail: Any
    on_disconnect: Any
    connect_timeout: float

    def username_pw_set(
        self,
        username: str | None,
        password: str | None = None,
    ) -> None: ...

    def will_set(
        self,
        topic: str,
        payload: str | bytes | None = None,
        qos: int = 0,
        retain: bool = False,
    ) -> None: ...

    def tls_set(
        self,
        ca_certs: str | None = None,
        certfile: str | None = None,
        keyfile: str | None = None,
    ) -> None: ...

    def tls_insecure_set(self, value: bool) -> None: ...

    def reconnect_delay_set(
        self,
        min_delay: int = 1,
        max_delay: int = 120,
    ) -> None: ...

    def connect_async(
        self,
        host: str,
        port: int = 1883,
        keepalive: int = 60,
    ) -> None: ...

    def loop_start(self) -> int: ...

    def loop_stop(self) -> int: ...

    def publish(
        self,
        topic: str,
        payload: str | bytes | None = None,
        qos: int = 0,
        retain: bool = False,
    ) -> PublishResult: ...

    def disconnect(self) -> int: ...


ClientFactory = Callable[[MqttSettings], MqttClient]
Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


def create_client(settings: MqttSettings) -> MqttClient:
    client = mqtt.Client(
        CallbackAPIVersion.VERSION2,
        client_id=settings.client_id,
        clean_session=True,
        protocol=mqtt.MQTTv311,
    )
    client.connect_timeout = settings.connect_timeout_seconds
    client.reconnect_delay_set(
        settings.reconnect_min_seconds,
        settings.reconnect_max_seconds,
    )
    if settings.username is not None:
        client.username_pw_set(settings.username, settings.password)
    client.will_set(
        f"{settings.topic_prefix}/status/online",
        payload="false",
        qos=1,
        retain=True,
    )
    if settings.tls_enabled:
        client.tls_set(
            ca_certs=(
                None
                if settings.tls_ca_file is None
                else str(settings.tls_ca_file)
            ),
            certfile=(
                None
                if settings.tls_cert_file is None
                else str(settings.tls_cert_file)
            ),
            keyfile=(
                None
                if settings.tls_key_file is None
                else str(settings.tls_key_file)
            ),
        )
        if settings.tls_insecure:
            LOGGER.warning(
                "MQTT TLS hostname verification is explicitly disabled",
            )
            client.tls_insecure_set(True)
    return cast(MqttClient, client)


class MqttPublisher:
    """Paho lifecycle and non-blocking snapshot publication."""

    def __init__(
        self,
        settings: MqttSettings,
        serializer: SnapshotSerializer,
        health: MqttHealthStore,
        refresh_interval_seconds: float,
        *,
        client_factory: ClientFactory = create_client,
        clock: Clock = utc_now,
    ) -> None:
        self._settings = settings
        self._serializer = serializer
        self._health = health
        self._refresh_interval = refresh_interval_seconds
        self._client_factory = client_factory
        self._clock = clock
        self._client: MqttClient | None = None
        self._wakeup: asyncio.Event | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task[None] | None = None
        self._stopping = False

    @property
    def enabled(self) -> bool:
        return self._settings.enabled

    def _wake(self) -> None:
        if self._loop is not None and self._wakeup is not None:
            self._loop.call_soon_threadsafe(self._wakeup.set)

    def notify_state(self, _state: CurrentState) -> None:
        self._wake()

    def _on_connect(
        self,
        _client: MqttClient,
        _userdata: Any,
        _flags: Any,
        reason_code: Any,
        _properties: Any,
    ) -> None:
        if reason_code == 0:
            self._health.connected(self._clock().astimezone(UTC))
            self._wake()
            return
        self._health.disconnected(
            self._clock().astimezone(UTC),
            "MQTT broker rejected the connection",
        )

    def _on_connect_fail(
        self,
        _client: MqttClient,
        _userdata: Any,
    ) -> None:
        self._health.disconnected(
            self._clock().astimezone(UTC),
            "MQTT broker unavailable",
        )

    def _on_disconnect(
        self,
        _client: MqttClient,
        _userdata: Any,
        _flags: Any,
        reason_code: Any,
        _properties: Any,
    ) -> None:
        if self._stopping:
            return
        self._health.disconnected(
            self._clock().astimezone(UTC),
            (
                "MQTT connection lost"
                if reason_code != 0
                else "MQTT broker disconnected"
            ),
        )

    def _publish(self, publication: Publication) -> PublishResult:
        if self._client is None:
            raise RuntimeError("MQTT client is not running")
        result = self._client.publish(
            publication.topic,
            publication.payload,
            qos=publication.qos,
            retain=publication.retain,
        )
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError("MQTT publication failed")
        return result

    def publish_snapshot(self) -> None:
        if not self._health.get().connected:
            return
        try:
            for publication in self._serializer.serialize():
                self._publish(publication)
            self._publish(
                Publication(
                    topic=f"{self._settings.topic_prefix}/status/online",
                    payload=b"true",
                ),
            )
        except (OSError, RuntimeError, ValueError):
            self._health.disconnected(
                self._clock().astimezone(UTC),
                "MQTT publication failed",
            )

    async def _run(self) -> None:
        if self._wakeup is None:
            raise RuntimeError("MQTT wakeup event is unavailable")
        while True:
            try:
                await asyncio.wait_for(
                    self._wakeup.wait(),
                    timeout=self._refresh_interval,
                )
            except TimeoutError:
                pass
            self._wakeup.clear()
            self.publish_snapshot()

    async def start(self) -> None:
        if not self._settings.enabled or self._client is not None:
            return
        if self._settings.host is None:
            raise RuntimeError("validated MQTT host is unavailable")
        self._loop = asyncio.get_running_loop()
        self._wakeup = asyncio.Event()
        self._stopping = False
        self._health.connecting()
        try:
            client = self._client_factory(self._settings)
            self._client = client
            client.on_connect = self._on_connect
            client.on_connect_fail = self._on_connect_fail
            client.on_disconnect = self._on_disconnect
            client.connect_async(
                self._settings.host,
                self._settings.port,
                self._settings.keepalive_seconds,
            )
            if client.loop_start() != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError("MQTT network loop failed to start")
        except (OSError, RuntimeError, ValueError):
            self._client = None
            self._health.disconnected(
                self._clock().astimezone(UTC),
                "MQTT broker unavailable",
            )
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        client, self._client = self._client, None
        if client is None:
            return
        self._stopping = True
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if self._health.get().connected:
            result = client.publish(
                f"{self._settings.topic_prefix}/status/online",
                b"false",
                qos=1,
                retain=True,
            )
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                try:
                    await asyncio.to_thread(
                        result.wait_for_publish,
                        self._settings.connect_timeout_seconds,
                    )
                except (OSError, RuntimeError, ValueError, TimeoutError):
                    pass
        client.disconnect()
        await asyncio.to_thread(client.loop_stop)
