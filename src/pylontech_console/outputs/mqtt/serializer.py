import json
import math
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pylontech_console.domain.current_state import CurrentState, CurrentValue
from pylontech_console.domain.discovery import TopologyEvent
from pylontech_console.mqtt_health import MqttHealthStore
from pylontech_console.outputs.api.query import StateQuery


@dataclass(frozen=True)
class Publication:
    topic: str
    payload: bytes
    qos: int = 1
    retain: bool = True


def encode_topic_level(value: str) -> str:
    allowed = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_."
    return "".join(
        chr(byte) if byte in allowed else f"%{byte:02X}"
        for byte in value.encode("utf-8")
    )


def _timestamp(value: datetime) -> str:
    utc = value.astimezone(UTC)
    return utc.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _scalar(value: Any) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    if isinstance(value, bool):
        return b"true" if value else b"false"
    if isinstance(value, datetime):
        return _timestamp(value).encode()
    if isinstance(value, Enum):
        return str(value.value).encode()
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("MQTT payload must be finite")
        return json.dumps(value, allow_nan=False, separators=(",", ":")).encode()
    if isinstance(value, (dict, list, tuple)):
        return _json(value).encode()
    return str(value).encode()


def _error_document(error: Any) -> dict[str, Any]:
    return {
        "barcode": error.barcode,
        "detail": error.detail,
        "group": error.group,
        "position": error.position,
        "timestamp": _timestamp(error.timestamp),
    }


def _event_document(event: TopologyEvent) -> dict[str, Any]:
    return {
        "barcode": event.barcode,
        "detail": event.detail,
        "kind": event.kind.value,
        "position": event.position,
        "previous_position": event.previous_position,
        "replaced_barcode": event.replaced_barcode,
        "timestamp": _timestamp(event.timestamp),
    }


def _event_key(event: TopologyEvent) -> tuple[Any, ...]:
    return (
        event.kind,
        event.timestamp,
        event.detail,
        event.barcode,
        event.position,
        event.previous_position,
        event.replaced_barcode,
    )


class SnapshotSerializer:
    """Serialize one shared state snapshot into the MQTT v0.1 topic tree."""

    def __init__(
        self,
        query: StateQuery,
        mqtt_health: MqttHealthStore,
        topic_prefix: str,
    ) -> None:
        self._query = query
        self._mqtt_health = mqtt_health
        self._prefix = topic_prefix
        self._position_topics: set[str] = set()
        self._cell_topics: set[str] = set()
        self._seen_events: set[tuple[Any, ...]] = set()

    def _topic(self, suffix: str) -> str:
        return f"{self._prefix}/{suffix}"

    def _publication(
        self,
        suffix: str,
        value: Any,
        *,
        retain: bool = True,
    ) -> Publication:
        return Publication(
            topic=self._topic(suffix),
            payload=_scalar(value),
            retain=retain,
        )

    def _metadata(
        self,
        group: str,
        value: CurrentValue[Any],
        snapshot_at: datetime,
    ) -> list[Publication]:
        metadata = self._query.metadata(value, snapshot_at)
        return [
            self._publication(f"{group}/meta/received_at", metadata.received_at),
            self._publication(f"{group}/meta/age_seconds", metadata.age_seconds),
            self._publication(f"{group}/meta/valid", metadata.valid),
            self._publication(f"{group}/meta/stale", metadata.stale),
            self._publication(
                f"{group}/meta/error",
                None if metadata.error is None else metadata.error.detail,
            ),
        ]

    def _finish_group(
        self,
        values: list[Publication],
        group: str,
        snapshot_at: datetime,
    ) -> None:
        values.append(
            self._publication(f"{group}/meta/snapshot_at", snapshot_at),
        )

    def _service(
        self,
        state: CurrentState,
        snapshot_at: datetime,
    ) -> list[Publication]:
        health = self._query.health_for(state, snapshot_at)
        mqtt = self._mqtt_health.get()
        errors = [_error_document(error) for error in state.errors]
        current_error = (
            mqtt.error
            if mqtt.enabled and not mqtt.connected
            else (state.errors[0].detail if state.errors else None)
        )
        return [
            self._publication("status/state", health.status),
            self._publication("status/updated_at", state.updated_at),
            self._publication("status/last_success_at", state.last_success_at),
            self._publication(
                "status/consecutive_failures",
                state.consecutive_failures,
            ),
            self._publication("status/error", current_error),
            self._publication("status/errors", errors),
            self._publication("status/snapshot_at", snapshot_at),
        ]

    def _inventory(
        self,
        state: CurrentState,
        snapshot_at: datetime,
    ) -> list[Publication]:
        values = self._metadata(
            "inventory",
            state.inventory_freshness,
            snapshot_at,
        )
        barcodes = sorted(state.inventory.modules)
        positions = {
            str(position): barcode
            for position, barcode in sorted(state.inventory.positions.items())
        }
        values.extend(
            [
                self._publication("inventory/modules", barcodes),
                self._publication(
                    "rack/positions",
                    json.dumps(
                        positions,
                        ensure_ascii=False,
                        allow_nan=False,
                        separators=(",", ":"),
                    ).encode(),
                ),
            ],
        )
        current_position_topics = {
            self._topic(f"rack/positions/{position}/barcode")
            for position in state.inventory.positions
        }
        values.extend(
            Publication(topic=topic, payload=b"")
            for topic in sorted(self._position_topics - current_position_topics)
        )
        values.extend(
            self._publication(
                f"rack/positions/{position}/barcode",
                barcode,
            )
            for position, barcode in sorted(state.inventory.positions.items())
        )
        self._position_topics = current_position_topics
        for barcode, record in sorted(state.inventory.modules.items()):
            root = f"modules/{encode_topic_level(barcode)}"
            values.extend(
                [
                    self._publication(f"{root}/barcode", barcode),
                    self._publication(f"{root}/present", record.present),
                    self._publication(f"{root}/position", record.current_position),
                    self._publication(
                        f"{root}/first_seen_at",
                        record.first_seen_at,
                    ),
                    self._publication(f"{root}/last_seen_at", record.last_seen_at),
                ],
            )
            identity = record.identity
            identity_fields: dict[str, Any] = {
                field.name: getattr(identity, field.name)
                for field in fields(identity)
                if field.name not in {"raw_payload", "barcode", "position", "received_at"}
            }
            identity_fields["release_date"] = identity_fields.pop(
                "release_date_raw",
            )
            identity_fields["extra_fields"] = dict(identity.extra_fields)
            values.extend(
                self._publication(f"{root}/identity/{name}", field_value)
                for name, field_value in identity_fields.items()
            )
        self._finish_group(values, "inventory", snapshot_at)
        return values

    def _rack(
        self,
        state: CurrentState,
        snapshot_at: datetime,
    ) -> list[Publication]:
        values = self._metadata("rack", state.rack, snapshot_at)
        rack = state.rack.value
        if rack is not None:
            rack_fields = {
                field.name: getattr(rack, field.name)
                for field in fields(rack)
                if field.name != "raw_payload"
            }
            rack_fields["extra_fields"] = dict(rack.extra_fields)
            rack_fields["derived/power_w"] = (
                rack.voltage_mv * rack.current_ma / 1_000_000
            )
            rack_fields["derived/cell_voltage_delta_mv"] = (
                rack.highest_cell_voltage_mv - rack.lowest_cell_voltage_mv
            )
            values.extend(
                self._publication(f"rack/system/{name}", field_value)
                for name, field_value in rack_fields.items()
            )
        self._finish_group(values, "rack", snapshot_at)
        return values

    def _modules(
        self,
        state: CurrentState,
        snapshot_at: datetime,
    ) -> list[Publication]:
        values: list[Publication] = []
        current_cell_topics: set[str] = set()
        for barcode, record in sorted(state.inventory.modules.items()):
            root = f"modules/{encode_topic_level(barcode)}"
            current = state.modules.get(barcode)
            if current is None:
                continue
            values.extend(
                self._metadata(f"{root}/detail", current.detail, snapshot_at),
            )
            detail = current.detail.value
            if detail is not None:
                detail_fields = {
                    field.name: getattr(detail, field.name)
                    for field in fields(detail)
                    if field.name != "raw_payload"
                }
                detail_fields["enabled_protections"] = list(
                    detail.enabled_protections,
                )
                detail_fields["extra_fields"] = dict(detail.extra_fields)
                values.extend(
                    self._publication(f"{root}/detail/{name}", field_value)
                    for name, field_value in detail_fields.items()
                )
            self._finish_group(values, f"{root}/detail", snapshot_at)

            values.extend(
                self._metadata(f"{root}/cells", current.cells, snapshot_at),
            )
            cells = current.cells.value
            if cells is not None:
                voltages = [cell.voltage_mv for cell in cells.cells]
                temperatures = [cell.temperature_mc for cell in cells.cells]
                derived = {
                    "minimum_voltage_mv": min(voltages) if voltages else None,
                    "maximum_voltage_mv": max(voltages) if voltages else None,
                    "voltage_delta_mv": (
                        max(voltages) - min(voltages) if voltages else None
                    ),
                    "minimum_temperature_mc": (
                        min(temperatures) if temperatures else None
                    ),
                    "maximum_temperature_mc": (
                        max(temperatures) if temperatures else None
                    ),
                }
                values.append(
                    self._publication(f"{root}/cells/count", len(cells.cells)),
                )
                values.extend(
                    self._publication(
                        f"{root}/cells/derived/{name}",
                        field_value,
                    )
                    for name, field_value in derived.items()
                )
                for cell in cells.cells:
                    cell_root = f"{root}/cells/{cell.index}"
                    cell_fields = asdict(cell)
                    cell_fields.pop("index")
                    for name, field_value in cell_fields.items():
                        topic = self._topic(f"{cell_root}/{name}")
                        current_cell_topics.add(topic)
                        values.append(
                            Publication(topic=topic, payload=_scalar(field_value)),
                        )
            self._finish_group(values, f"{root}/cells", snapshot_at)

        values.extend(
            Publication(topic=topic, payload=b"")
            for topic in sorted(self._cell_topics - current_cell_topics)
        )
        self._cell_topics = current_cell_topics
        return values

    def _events(self, state: CurrentState) -> list[Publication]:
        values: list[Publication] = []
        for event in state.topology_events:
            key = _event_key(event)
            if key in self._seen_events:
                continue
            values.append(
                self._publication(
                    "events/topology",
                    _event_document(event),
                    retain=False,
                ),
            )
            self._seen_events.add(key)
        return values

    def serialize(self) -> tuple[Publication, ...]:
        state, snapshot_at = self._query.snapshot()
        return tuple(
            self._service(state, snapshot_at)
            + self._inventory(state, snapshot_at)
            + self._rack(state, snapshot_at)
            + self._modules(state, snapshot_at)
            + self._events(state),
        )
