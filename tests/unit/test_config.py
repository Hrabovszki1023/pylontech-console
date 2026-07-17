import pytest
from pydantic import ValidationError

from pylontech_console.config import WaveshareSettings, load_waveshare_settings

ENVIRONMENT_VARIABLES = (
    "PYLONTECH_WAVESHARE_HOST",
    "PYLONTECH_WAVESHARE_PORT",
    "PYLONTECH_WAVESHARE_CONNECT_TIMEOUT_SECONDS",
    "PYLONTECH_WAVESHARE_RESPONSE_TIMEOUT_SECONDS",
)


def clear_waveshare_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)


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
    assert settings.response_timeout_seconds == 3


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
