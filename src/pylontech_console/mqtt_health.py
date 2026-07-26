from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from threading import Lock


class MqttConnectionState(str, Enum):
    DISABLED = "disabled"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


@dataclass(frozen=True)
class MqttHealth:
    enabled: bool
    state: MqttConnectionState
    connected: bool
    last_connected_at: datetime | None = None
    last_disconnected_at: datetime | None = None
    consecutive_failures: int = 0
    error: str | None = None

    @classmethod
    def disabled(cls) -> "MqttHealth":
        return cls(
            enabled=False,
            state=MqttConnectionState.DISABLED,
            connected=False,
        )

    @classmethod
    def connecting(cls) -> "MqttHealth":
        return cls(
            enabled=True,
            state=MqttConnectionState.CONNECTING,
            connected=False,
        )


class MqttHealthStore:
    """Thread-safe MQTT runtime health shared with output queries."""

    def __init__(self, initial: MqttHealth | None = None) -> None:
        self._value = initial or MqttHealth.disabled()
        self._lock = Lock()

    def get(self) -> MqttHealth:
        with self._lock:
            return self._value

    def set(self, value: MqttHealth) -> None:
        with self._lock:
            self._value = value

    def connected(self, now: datetime) -> None:
        with self._lock:
            self._value = replace(
                self._value,
                enabled=True,
                state=MqttConnectionState.CONNECTED,
                connected=True,
                last_connected_at=now,
                consecutive_failures=0,
                error=None,
            )

    def connecting(self) -> None:
        with self._lock:
            self._value = replace(
                self._value,
                enabled=True,
                state=MqttConnectionState.CONNECTING,
                connected=False,
            )

    def disconnected(self, now: datetime, error: str) -> None:
        with self._lock:
            self._value = replace(
                self._value,
                enabled=True,
                state=MqttConnectionState.DISCONNECTED,
                connected=False,
                last_disconnected_at=now,
                consecutive_failures=self._value.consecutive_failures + 1,
                error=error,
            )
