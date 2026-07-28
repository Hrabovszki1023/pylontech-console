from pathlib import Path

import pytest
from pydantic import ValidationError

from pylontech_console.config import (
    ConsoleSettings,
    HttpSettings,
    MqttSettings,
    PollingSettings,
    WebSettings,
    WaveshareSettings,
    load_polling_settings,
    load_console_settings,
    load_mqtt_settings,
    load_waveshare_settings,
    load_web_settings,
)

ENVIRONMENT_VARIABLES = (
    "PYLONTECH_WAVESHARE_HOST",
    "PYLONTECH_WAVESHARE_PORT",
    "PYLONTECH_WAVESHARE_CONNECT_TIMEOUT_SECONDS",
    "PYLONTECH_WAVESHARE_RESPONSE_TIMEOUT_SECONDS",
)
CONSOLE_ENVIRONMENT_VARIABLES = (
    "PYLONTECH_CONSOLE_LOGIN_PASSWORD",
    "PYLONTECH_CONSOLE_LOGIN_PASSWORD_FILE",
)
PROJECT_ROOT = Path(__file__).parents[2]


def clear_waveshare_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def clear_console_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in CONSOLE_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def test_console_password_loads_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_console_environment(monkeypatch)
    monkeypatch.setenv("PYLONTECH_CONSOLE_LOGIN_PASSWORD", "secret")

    settings = load_console_settings()

    assert settings.password() == "secret"
    assert "secret" not in repr(settings)


def test_console_password_loads_from_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    clear_console_environment(monkeypatch)
    password_file = tmp_path / "console-password"
    password_file.write_bytes(b"secret\r\n")
    monkeypatch.setenv(
        "PYLONTECH_CONSOLE_LOGIN_PASSWORD_FILE",
        str(password_file),
    )

    assert load_console_settings().password() == "secret"


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"login_password": "secret", "login_password_file": "secret.txt"},
        {"login_password": ""},
        {"login_password": "line\nbreak"},
        {"login_password": "nul\x00byte"},
        {"login_password": "pässword"},
    ],
)
def test_console_rejects_invalid_configuration(
    values: dict[str, object],
) -> None:
    with pytest.raises((ValidationError, ValueError)):
        ConsoleSettings.model_validate(values)


def test_compose_passes_console_secret_sources() -> None:
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "PYLONTECH_CONSOLE_LOGIN_PASSWORD:" in compose
    assert "PYLONTECH_CONSOLE_LOGIN_PASSWORD_FILE:" in compose


def test_loads_values_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_waveshare_environment(monkeypatch)
    monkeypatch.setenv("PYLONTECH_WAVESHARE_HOST", "gateway.local")
    monkeypatch.setenv("PYLONTECH_WAVESHARE_PORT", "5000")
    monkeypatch.setenv("PYLONTECH_WAVESHARE_CONNECT_TIMEOUT_SECONDS", "1.5")
    monkeypatch.setenv("PYLONTECH_WAVESHARE_RESPONSE_TIMEOUT_SECONDS", "2.5")

    settings = load_waveshare_settings()

    assert settings.host == "gateway.local"
    assert settings.port == 5000
    assert settings.connect_timeout_seconds == 1.5
    assert settings.response_timeout_seconds == 2.5


def test_uses_documented_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_waveshare_environment(monkeypatch)
    monkeypatch.setenv("PYLONTECH_WAVESHARE_HOST", "gateway.local")

    settings = load_waveshare_settings()

    assert settings.port == 4196
    assert settings.connect_timeout_seconds == 5
    assert settings.response_timeout_seconds == 5


def test_rejects_missing_host(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_waveshare_environment(monkeypatch)

    with pytest.raises(ValidationError, match="host"):
        load_waveshare_settings()


@pytest.mark.parametrize("host", ["", "   "])
def test_rejects_empty_host(host: str) -> None:
    with pytest.raises(ValidationError, match="host"):
        WaveshareSettings(host=host)


@pytest.mark.parametrize("port", [0, 65536])
def test_rejects_port_outside_valid_range(port: int) -> None:
    with pytest.raises(ValidationError, match="port"):
        WaveshareSettings(host="gateway.local", port=port)


@pytest.mark.parametrize(
    "field",
    ["connect_timeout_seconds", "response_timeout_seconds"],
)
@pytest.mark.parametrize("value", [0, -1])
def test_rejects_non_positive_timeout(field: str, value: int) -> None:
    with pytest.raises(ValidationError, match=field):
        WaveshareSettings(host="gateway.local", **{field: value})


def test_polling_uses_documented_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "PYLONTECH_POLLING_RACK_INTERVAL_SECONDS",
        "PYLONTECH_POLLING_MODULE_INTERVAL_SECONDS",
        "PYLONTECH_POLLING_INVENTORY_INTERVAL_SECONDS",
        "PYLONTECH_POLLING_STALE_AFTER_MULTIPLIER",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = load_polling_settings()

    assert settings.rack_interval_seconds == 5
    assert settings.module_interval_seconds == 60
    assert settings.inventory_interval_seconds == 300
    assert settings.stale_after_multiplier == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("rack_interval_seconds", 0),
        ("module_interval_seconds", -1),
        ("inventory_interval_seconds", float("inf")),
        ("stale_after_multiplier", 0.9),
        ("stale_after_multiplier", float("nan")),
    ],
)
def test_polling_rejects_invalid_values(field: str, value: float) -> None:
    with pytest.raises(ValidationError, match=field):
        PollingSettings(**{field: value})


def test_http_uses_documented_defaults() -> None:
    settings = HttpSettings()

    assert settings.host == "0.0.0.0"
    assert settings.port == 8000


@pytest.mark.parametrize("host", ["", "   "])
def test_http_rejects_empty_host(host: str) -> None:
    with pytest.raises(ValidationError, match="host"):
        HttpSettings(host=host)


@pytest.mark.parametrize("port", [0, 65536])
def test_http_rejects_invalid_port(port: int) -> None:
    with pytest.raises(ValidationError, match="port"):
        HttpSettings(port=port)


def test_web_uses_documented_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "PYLONTECH_WEB_HEATMAP_DEADBAND_MV",
        "PYLONTECH_WEB_HEATMAP_SCALE_MV",
        "PYLONTECH_WEB_CELL_LOW_WARNING_MV",
        "PYLONTECH_WEB_CELL_LOW_CRITICAL_MV",
        "PYLONTECH_WEB_CELL_HIGH_BALANCING_MV",
        "PYLONTECH_WEB_CELL_HIGH_WARNING_MV",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = load_web_settings()

    assert settings.heatmap_deadband_mv == 2
    assert settings.heatmap_scale_mv == 50
    assert settings.cell_low_warning_mv == 3100
    assert settings.cell_low_critical_mv == 3000
    assert settings.cell_high_balancing_mv == 3547
    assert settings.cell_high_warning_mv == 3600


def test_web_loads_environment_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYLONTECH_WEB_HEATMAP_DEADBAND_MV", "3")
    monkeypatch.setenv("PYLONTECH_WEB_HEATMAP_SCALE_MV", "60")
    monkeypatch.setenv("PYLONTECH_WEB_CELL_LOW_WARNING_MV", "3110")
    monkeypatch.setenv("PYLONTECH_WEB_CELL_LOW_CRITICAL_MV", "3010")
    monkeypatch.setenv("PYLONTECH_WEB_CELL_HIGH_BALANCING_MV", "3550")
    monkeypatch.setenv("PYLONTECH_WEB_CELL_HIGH_WARNING_MV", "3610")

    settings = load_web_settings()

    assert settings == WebSettings(
        heatmap_deadband_mv=3,
        heatmap_scale_mv=60,
        cell_low_warning_mv=3110,
        cell_low_critical_mv=3010,
        cell_high_balancing_mv=3550,
        cell_high_warning_mv=3610,
    )


@pytest.mark.parametrize(
    "values",
    [
        {"heatmap_deadband_mv": -1},
        {"heatmap_scale_mv": 0},
        {"heatmap_deadband_mv": 50},
        {"cell_low_critical_mv": 3100},
        {"cell_low_warning_mv": 3547},
        {"cell_high_balancing_mv": 3600},
    ],
)
def test_web_rejects_invalid_values(values: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        WebSettings(**values)


def test_mqtt_uses_safe_disabled_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "PYLONTECH_MQTT_ENABLED",
        "PYLONTECH_MQTT_HOST",
        "PYLONTECH_MQTT_PORT",
        "PYLONTECH_MQTT_CLIENT_ID",
        "PYLONTECH_MQTT_TOPIC_PREFIX",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = load_mqtt_settings()

    assert settings.enabled is False
    assert settings.host is None
    assert settings.port == 1883
    assert settings.client_id == "pylontech-console"
    assert settings.topic_prefix == "pylontech"


def test_mqtt_loads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYLONTECH_MQTT_ENABLED", "true")
    monkeypatch.setenv("PYLONTECH_MQTT_HOST", " broker.local ")
    monkeypatch.setenv("PYLONTECH_MQTT_PORT", "1884")
    monkeypatch.setenv("PYLONTECH_MQTT_USERNAME", "user")
    monkeypatch.setenv("PYLONTECH_MQTT_PASSWORD", "secret")
    monkeypatch.setenv("PYLONTECH_MQTT_TOPIC_PREFIX", "home/battery")

    settings = load_mqtt_settings()

    assert settings.enabled is True
    assert settings.host == "broker.local"
    assert settings.port == 1884
    assert settings.username == "user"
    assert settings.password == "secret"
    assert settings.topic_prefix == "home/battery"


@pytest.mark.parametrize(
    "values",
    [
        {"enabled": True},
        {"port": 0},
        {"client_id": ""},
        {"client_id": "x" * 129},
        {"topic_prefix": "/pylontech"},
        {"topic_prefix": "pylontech/"},
        {"topic_prefix": "pylontech//rack"},
        {"topic_prefix": "pylontech/#"},
        {"password": "secret"},
        {"reconnect_min_seconds": 10, "reconnect_max_seconds": 5},
        {"connect_timeout_seconds": float("inf")},
        {"tls_insecure": True},
        {"tls_cert_file": "cert.pem"},
    ],
)


def test_mqtt_rejects_invalid_configuration(
    values: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        MqttSettings.model_validate(values)


def test_compose_passes_every_mqtt_contract_variable() -> None:
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    expected = {
        "ENABLED",
        "HOST",
        "PORT",
        "CLIENT_ID",
        "USERNAME",
        "PASSWORD",
        "TOPIC_PREFIX",
        "KEEPALIVE_SECONDS",
        "CONNECT_TIMEOUT_SECONDS",
        "RECONNECT_MIN_SECONDS",
        "RECONNECT_MAX_SECONDS",
        "TLS_ENABLED",
        "TLS_CA_FILE",
        "TLS_CERT_FILE",
        "TLS_KEY_FILE",
        "TLS_INSECURE",
    }

    assert {
        suffix
        for suffix in expected
        if f"PYLONTECH_MQTT_{suffix}:" in compose
    } == expected
