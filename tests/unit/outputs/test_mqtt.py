import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

import paho.mqtt.client as mqtt
import pytest

from pylontech_console.config import MqttSettings
from pylontech_console.domain.discovery import (
    TopologyEvent,
    TopologyEventKind,
)
from pylontech_console.mqtt_health import (
    MqttConnectionState,
    MqttHealth,
    MqttHealthStore,
)
from pylontech_console.outputs.api.query import StateQuery
from pylontech_console.outputs.mqtt.publisher import MqttPublisher
from pylontech_console.outputs.mqtt.serializer import (
    Publication,
    SnapshotSerializer,
    encode_topic_level,
)
from tests.web_fixture import SNAPSHOT_TIME, create_web_test_app


def serializer(
    health: MqttHealth | None = None,
) -> tuple[SnapshotSerializer, Any]:
    app = create_web_test_app()
    store = app.state.current_state_store
    health_store = MqttHealthStore(
        health
        or MqttHealth(
            enabled=True,
            state=MqttConnectionState.CONNECTED,
            connected=True,
            last_connected_at=SNAPSHOT_TIME,
        ),
    )
    query = StateQuery(
        store,
        clock=lambda: SNAPSHOT_TIME,
        mqtt_health=health_store,
    )
    return SnapshotSerializer(query, health_store, "pylontech"), store


def publications_by_topic(
    values: tuple[Publication, ...],
) -> dict[str, Publication]:
    return {value.topic: value for value in values}


def test_snapshot_serializes_exact_state_topics_without_raw_payload() -> None:
    mqtt_serializer, _store = serializer()

    values = mqtt_serializer.serialize()
    topics = publications_by_topic(values)

    assert topics["pylontech/status/state"].payload == b"online"
    assert topics["pylontech/inventory/modules"].payload == (
        b'["MODULE-A","MODULE-B"]'
    )
    assert topics["pylontech/rack/positions"].payload == (
        b'{"1":"MODULE-A","2":"MODULE-B"}'
    )
    assert topics["pylontech/rack/system/voltage_mv"].payload == b"50000"
    assert topics["pylontech/rack/system/derived/power_w"].payload == b"650.0"
    assert topics[
        "pylontech/modules/MODULE-A/detail/voltage_mv"
    ].payload == b"49950"
    assert topics[
        "pylontech/modules/MODULE-A/cells/0/voltage_mv"
    ].payload == b"3329"
    assert topics[
        "pylontech/modules/MODULE-A/cells/derived/voltage_delta_mv"
    ].payload == b"2"
    assert topics[
        "pylontech/modules/MODULE-A/cells/meta/valid"
    ].payload == b"true"
    assert topics[
        "pylontech/modules/MODULE-A/cells/meta/age_seconds"
    ].payload == b"5.0"
    assert all(value.qos == 1 for value in values)
    assert all(
        value.retain
        for value in values
        if value.topic != "pylontech/events/topology"
    )
    assert b"raw_payload" not in b"".join(value.payload for value in values)
    assert b"secret" not in b"".join(value.payload for value in values)


def test_barcode_encoding_is_reversible_and_collision_free() -> None:
    assert encode_topic_level("ABC-_.123") == "ABC-_.123"
    assert encode_topic_level("A/B% +#") == "A%2FB%25%20%2B%23"
    assert encode_topic_level("ä") == "%C3%A4"
    assert encode_topic_level("A/B") != encode_topic_level("A%2FB")


def test_position_move_keeps_module_topics_and_deletes_old_mapping() -> None:
    mqtt_serializer, store = serializer()
    first = mqtt_serializer.serialize()
    state = store.get()
    inventory = state.inventory
    records = dict(inventory.modules)
    records["MODULE-A"] = replace(
        records["MODULE-A"],
        current_position=9,
    )
    moved = replace(
        inventory,
        positions=MappingProxyType({2: "MODULE-B", 9: "MODULE-A"}),
        modules=MappingProxyType(records),
    )
    store.publish(
        replace(
            state,
            inventory=moved,
            inventory_freshness=replace(
                state.inventory_freshness,
                value=moved,
            ),
        ),
    )

    second = mqtt_serializer.serialize()
    topics = publications_by_topic(second)

    assert any(
        value.topic.startswith("pylontech/modules/MODULE-A/")
        for value in first
    )
    assert topics["pylontech/rack/positions/1/barcode"].payload == b""
    assert topics["pylontech/rack/positions/9/barcode"].payload == b"MODULE-A"
    assert topics["pylontech/modules/MODULE-A/position"].payload == b"9"


def test_topology_events_are_non_retained_and_not_replayed() -> None:
    mqtt_serializer, store = serializer()
    state = store.get()
    event = TopologyEvent(
        TopologyEventKind.MODULE_MOVED,
        SNAPSHOT_TIME,
        "module moved",
        "MODULE-A",
        9,
        1,
    )
    store.publish(replace(state, topology_events=(event,)))

    first = mqtt_serializer.serialize()
    second = mqtt_serializer.serialize()
    events = [
        value
        for value in first
        if value.topic == "pylontech/events/topology"
    ]

    assert len(events) == 1
    assert events[0].retain is False
    assert b'"kind":"MODULE_MOVED"' in events[0].payload
    assert all(
        value.topic != "pylontech/events/topology"
        for value in second
    )


class FakePublishResult:
    def __init__(self, rc: int = mqtt.MQTT_ERR_SUCCESS) -> None:
        self.rc = rc
        self.waited = False

    def wait_for_publish(self, timeout: float | None = None) -> None:
        self.waited = True


class FakeClient:
    def __init__(self) -> None:
        self.on_connect: Any = None
        self.on_connect_fail: Any = None
        self.on_disconnect: Any = None
        self.connect_timeout = 0.0
        self.connected_with: tuple[str, int, int] | None = None
        self.publications: list[tuple[str, bytes, int, bool]] = []
        self.loop_started = False
        self.loop_stopped = False
        self.disconnected = False

    def username_pw_set(
        self,
        username: str | None,
        password: str | None = None,
    ) -> None:
        pass

    def will_set(
        self,
        topic: str,
        payload: str | bytes | None = None,
        qos: int = 0,
        retain: bool = False,
    ) -> None:
        pass

    def tls_set(
        self,
        ca_certs: str | None = None,
        certfile: str | None = None,
        keyfile: str | None = None,
    ) -> None:
        pass

    def tls_insecure_set(self, value: bool) -> None:
        pass

    def reconnect_delay_set(
        self,
        min_delay: int = 1,
        max_delay: int = 120,
    ) -> None:
        pass

    def connect_async(
        self,
        host: str,
        port: int = 1883,
        keepalive: int = 60,
    ) -> None:
        self.connected_with = (host, port, keepalive)

    def loop_start(self) -> int:
        self.loop_started = True
        return mqtt.MQTT_ERR_SUCCESS

    def loop_stop(self) -> int:
        self.loop_stopped = True
        return mqtt.MQTT_ERR_SUCCESS

    def publish(
        self,
        topic: str,
        payload: str | bytes | None = None,
        qos: int = 0,
        retain: bool = False,
    ) -> FakePublishResult:
        payload_bytes = (
            b""
            if payload is None
            else payload.encode() if isinstance(payload, str) else payload
        )
        self.publications.append((topic, payload_bytes, qos, retain))
        return FakePublishResult()

    def disconnect(self) -> int:
        self.disconnected = True
        return mqtt.MQTT_ERR_SUCCESS


@pytest.mark.asyncio
async def test_publisher_lifecycle_reconnect_and_graceful_offline() -> None:
    mqtt_serializer, _store = serializer(MqttHealth.connecting())
    health = mqtt_serializer._mqtt_health
    fake = FakeClient()
    settings = MqttSettings(enabled=True, host="broker.local")
    now = datetime(2026, 7, 26, 10, 0, tzinfo=timezone.utc)
    publisher = MqttPublisher(
        settings,
        mqtt_serializer,
        health,
        60,
        client_factory=lambda _settings: fake,
        clock=lambda: now,
    )

    await publisher.start()
    try:
        assert fake.connected_with == ("broker.local", 1883, 60)
        assert fake.loop_started is True
        assert health.get().state is MqttConnectionState.CONNECTING

        fake.on_connect(fake, None, None, 0, None)
        for _ in range(100):
            if fake.publications:
                break
            await asyncio.sleep(0.01)
        assert health.get().state is MqttConnectionState.CONNECTED
        assert fake.publications[-1] == (
            "pylontech/status/online",
            b"true",
            1,
            True,
        )
        first_count = len(fake.publications)

        fake.on_disconnect(fake, None, None, 1, None)
        assert health.get().state is MqttConnectionState.DISCONNECTED
        fake.on_connect(fake, None, None, 0, None)
        for _ in range(100):
            if len(fake.publications) > first_count:
                break
            await asyncio.sleep(0.01)
        assert len(fake.publications) > first_count
    finally:
        await publisher.stop()

    assert fake.publications[-1] == (
        "pylontech/status/online",
        b"false",
        1,
        True,
    )
    assert fake.disconnected is True
    assert fake.loop_stopped is True


@pytest.mark.asyncio
async def test_disabled_publisher_creates_no_client() -> None:
    mqtt_serializer, _store = serializer(MqttHealth.disabled())
    created = False

    def factory(_settings: MqttSettings) -> FakeClient:
        nonlocal created
        created = True
        return FakeClient()

    publisher = MqttPublisher(
        MqttSettings(),
        mqtt_serializer,
        mqtt_serializer._mqtt_health,
        5,
        client_factory=factory,
    )

    await publisher.start()
    await publisher.stop()

    assert created is False


@pytest.mark.asyncio
async def test_broker_start_failure_is_reported_without_raising() -> None:
    mqtt_serializer, _store = serializer(MqttHealth.connecting())
    health = mqtt_serializer._mqtt_health

    def failing_factory(_settings: MqttSettings) -> FakeClient:
        raise OSError("secret-broker.internal:1883 refused password=secret")

    publisher = MqttPublisher(
        MqttSettings(enabled=True, host="broker.local"),
        mqtt_serializer,
        health,
        5,
        client_factory=failing_factory,
    )

    await publisher.start()

    assert health.get().state is MqttConnectionState.DISCONNECTED
    assert health.get().error == "MQTT broker unavailable"
    assert health.get().consecutive_failures == 1
    await publisher.stop()
