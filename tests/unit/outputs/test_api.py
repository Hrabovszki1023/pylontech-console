from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import MappingProxyType

from fastapi.testclient import TestClient

from pylontech_console.domain.current_state import (
    AcquisitionError,
    ConnectionState,
    CurrentModule,
    CurrentState,
    CurrentValue,
    readonly_modules,
)
from pylontech_console.domain.discovery import (
    InventoryState,
    ModuleRecord,
    TopologyEvent,
    TopologyEventKind,
)
from pylontech_console.domain.info import ModuleIdentity
from pylontech_console.domain.process import (
    CellMeasurement,
    ModuleCells,
    ModuleDetail,
    RackSummary,
)
from pylontech_console.outputs.api import create_application
from pylontech_console.mqtt_health import (
    MqttConnectionState,
    MqttHealth,
    MqttHealthStore,
)
from pylontech_console.outputs.api.query import StateQuery
from pylontech_console.polling import CurrentStateStore

T0 = datetime(2026, 7, 19, 14, 30, tzinfo=timezone.utc)
NOW = T0 + timedelta(seconds=10)


def identity() -> ModuleIdentity:
    return ModuleIdentity(
        T0, 1, "B1", "Pylon", "US2000C", "board", "main", "software",
        "boot", "communication", "20-12-11", "48V/50AH", 15, -90000,
        90000, 1200, 115200, MappingProxyType({"future": "value"}), "secret",
    )


def detail() -> ModuleDetail:
    return ModuleDetail(
        T0, 1, 50000, -1000, 25000, 80, 50000, 54000, 1, "Dischg",
        None, "Normal", "Normal", "Normal", "Normal", "Normal", "OFF",
        ("UV",), "0x0", 0, "0x0", 0, "0x0", 0, None,
        MappingProxyType({"future": "value"}), "secret",
    )


def cells() -> ModuleCells:
    return ModuleCells(
        T0,
        1,
        (
            CellMeasurement(
                0, 3300, -1000, 25000, "Dischg", "Normal", "Normal",
                "Normal", 80, 40000, "N",
            ),
            CellMeasurement(
                1, 3310, -1000, 26000, "Dischg", "Normal", "Normal",
                "Normal", 81, 40100, "Y",
            ),
        ),
        "secret",
    )


def rack() -> RackSummary:
    return RackSummary(
        T0, "Dischg", 1, 1, 0, 50000, -1000, 80000, 100000, 80, 95,
        3310, 3305, 3300, 26000, 25000, 24000, 53250, 46000, 10000,
        -25000, 53250, 46000, 20000, -50000,
        MappingProxyType({"future": "value"}), "secret",
    )


def client() -> TestClient:
    record = ModuleRecord("B1", identity(), 1, True, T0, T0, None)
    inventory = InventoryState(
        T0,
        MappingProxyType({1: "B1"}),
        MappingProxyType({"B1": record}),
    )
    current = CurrentModule(
        CurrentValue(detail(), T0, True, 60, 2),
        CurrentValue(cells(), T0, False, 5, 2, AcquisitionError(
            "cells", "cells acquisition failed", T0, "B1", 1,
        )),
    )
    state = replace(
        CurrentState.empty(5, 60, 300, 2),
        updated_at=T0,
        connection=ConnectionState.DEGRADED,
        last_success_at=T0,
        inventory=inventory,
        inventory_freshness=CurrentValue(inventory, T0, True, 300, 2),
        rack=CurrentValue(rack(), T0, True, 5, 2),
        modules=readonly_modules({"B1": current}),
        topology_events=(
            TopologyEvent(
                TopologyEventKind.MODULE_DISCOVERED, T0, "found", "B1", 1,
            ),
        ),
        errors=(AcquisitionError("cells", "cells acquisition failed", T0),),
    )
    return TestClient(
        create_application(CurrentStateStore(state), clock=lambda: NOW),
    )


def test_all_read_endpoints_and_serialization() -> None:
    api = client()
    health = api.get("/api/v1/health")
    rack_response = api.get("/api/v1/rack")
    positions = api.get("/api/v1/positions")
    modules = api.get("/api/v1/modules")
    module = api.get("/api/v1/modules/B1")
    position = api.get("/api/v1/positions/1")
    events = api.get("/api/v1/topology-events?limit=1")

    assert all(
        response.status_code == 200
        for response in (
            health, rack_response, positions, modules, module, position, events,
        )
    )
    assert rack_response.json()["age_seconds"] == 10
    assert rack_response.json()["stale"] is True
    assert rack_response.json()["value"]["derived"]["power_w"] == -50
    assert rack_response.json()["value"]["extra_fields"] == {"future": "value"}
    assert positions.json()["value"] == [{"position": 1, "barcode": "B1"}]
    assert modules.json()["modules"][0]["cells"]["derived"] == {
        "minimum_voltage_mv": 3300,
        "maximum_voltage_mv": 3310,
        "voltage_delta_mv": 10,
        "minimum_temperature_mc": 25000,
        "maximum_temperature_mc": 26000,
    }
    assert len(module.json()["cells"]["value"]) == 2
    assert "raw_payload" not in str(module.json())
    assert events.json()["events"][0]["kind"] == "MODULE_DISCOVERED"
    assert health.json()["mqtt"] == {
        "enabled": False,
        "state": "disabled",
        "connected": False,
        "last_connected_at": None,
        "last_disconnected_at": None,
        "consecutive_failures": 0,
        "error": None,
    }


def test_unknown_and_validation_behavior_and_no_write_routes() -> None:
    api = client()

    assert api.get("/api/v1/modules/unknown").status_code == 404
    assert api.get("/api/v1/positions/2").status_code == 404
    assert api.get("/api/v1/positions/17").status_code == 422
    assert api.get("/api/v1/topology-events?limit=0").status_code == 422
    assert api.post("/api/v1/rack").status_code == 405
    assert api.get("/api/v1/commands").status_code == 404


def test_empty_rack_and_inventory_are_invalid_stale_envelopes() -> None:
    state = CurrentState.empty(5, 60, 300, 2)
    api = TestClient(
        create_application(CurrentStateStore(state), clock=lambda: NOW),
    )

    rack_response = api.get("/api/v1/rack").json()
    positions_response = api.get("/api/v1/positions").json()

    assert rack_response["value"] is None
    assert rack_response["valid"] is False
    assert rack_response["stale"] is True
    assert positions_response["value"] is None


def test_application_lifecycle_starts_and_stops_runtime() -> None:
    calls: list[str] = []

    class Runtime:
        async def start(self) -> None:
            calls.append("start")

        async def stop(self) -> None:
            calls.append("stop")

    state = CurrentState.empty(5, 60, 300, 2)
    app = create_application(
        CurrentStateStore(state),
        clock=lambda: NOW,
        runtime=Runtime(),
    )

    with TestClient(app) as api:
        assert api.get("/api/v1/health").status_code == 200

    assert calls == ["start", "stop"]


def test_enabled_unconnected_mqtt_degrades_otherwise_online_health() -> None:
    state = replace(
        CurrentState.empty(5, 60, 300, 2),
        connection=ConnectionState.ONLINE,
    )
    store = CurrentStateStore(state)
    mqtt_health = MqttHealthStore(
        MqttHealth(
            enabled=True,
            state=MqttConnectionState.CONNECTING,
            connected=False,
        ),
    )
    query = StateQuery(store, clock=lambda: NOW, mqtt_health=mqtt_health)
    api = TestClient(create_application(store, query=query))

    response = api.get("/api/v1/health").json()

    assert response["status"] == "degraded"
    assert response["mqtt"]["state"] == "connecting"
