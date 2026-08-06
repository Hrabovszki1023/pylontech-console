import math
from pathlib import Path
from typing import Annotated

from pydantic import (
    Field,
    SecretStr,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class WaveshareSettings(BaseSettings):
    """Validated connection settings for the Waveshare gateway."""

    model_config = SettingsConfigDict(
        env_prefix="PYLONTECH_WAVESHARE_",
        extra="ignore",
    )

    host: NonEmptyString
    port: int = Field(default=4196, ge=1, le=65535)
    connect_timeout_seconds: float = Field(default=5, gt=0)
    response_timeout_seconds: float = Field(default=5, gt=0)


def load_waveshare_settings() -> WaveshareSettings:
    """Load Waveshare settings from the process environment."""

    return WaveshareSettings()  # type: ignore[call-arg]


def _validate_console_password(value: str) -> str:
    try:
        value.encode("ascii")
    except UnicodeEncodeError as error:
        raise ValueError("console login password must be strict ASCII") from error
    if not value or any(character in value for character in ("\r", "\n", "\x00")):
        raise ValueError(
            "console login password must be non-empty without CR, LF or NUL",
        )
    return value


class ConsoleSettings(BaseSettings):
    """Validated secret configuration for the Pylontech console session."""

    model_config = SettingsConfigDict(
        env_prefix="PYLONTECH_CONSOLE_",
        extra="ignore",
    )

    login_password: SecretStr | None = None
    login_password_file: Path | None = None

    @field_validator("login_password", mode="before")
    @classmethod
    def empty_password_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("login_password_file", mode="before")
    @classmethod
    def empty_path_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_credential_source(self) -> "ConsoleSettings":
        if (self.login_password is None) == (self.login_password_file is None):
            raise ValueError(
                "configure exactly one console login password source",
            )
        self.password()
        return self

    def password(self) -> str:
        if self.login_password is not None:
            return _validate_console_password(
                self.login_password.get_secret_value(),
            )
        path = self.login_password_file
        if path is None:
            raise ValueError("console login password is required")
        try:
            value = path.read_bytes()
        except OSError as error:
            raise ValueError("console login password file is not readable") from error
        if value.endswith(b"\r\n"):
            value = value[:-2]
        elif value.endswith((b"\r", b"\n")):
            value = value[:-1]
        try:
            decoded = value.decode("ascii")
        except UnicodeDecodeError as error:
            raise ValueError("console login password must be strict ASCII") from error
        return _validate_console_password(decoded)


def load_console_settings() -> ConsoleSettings:
    return ConsoleSettings()


class PollingSettings(BaseSettings):
    """Validated cyclic acquisition and freshness settings."""

    model_config = SettingsConfigDict(
        env_prefix="PYLONTECH_POLLING_",
        extra="ignore",
    )

    rack_interval_seconds: float = Field(default=5, ge=0)
    module_interval_seconds: float = Field(default=60, ge=0)
    inventory_interval_seconds: float = Field(default=300, ge=0)
    stale_after_multiplier: float = Field(default=2, ge=1)

    @field_validator(
        "rack_interval_seconds",
        "module_interval_seconds",
        "inventory_interval_seconds",
        "stale_after_multiplier",
    )
    @classmethod
    def finite_positive(cls, value: float) -> float:
        if not math.isfinite(value) or value <= 0:
            raise ValueError("polling values must be finite and positive")
        return value


def load_polling_settings() -> PollingSettings:
    """Load polling settings from the process environment."""

    return PollingSettings()


class HttpSettings(BaseSettings):
    """Validated HTTP bind settings."""

    model_config = SettingsConfigDict(
        env_prefix="PYLONTECH_HTTP_",
        extra="ignore",
    )

    host: NonEmptyString = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)


def load_http_settings() -> HttpSettings:
    return HttpSettings()


class WebSettings(BaseSettings):
    """Validated cell-voltage visualization settings."""

    model_config = SettingsConfigDict(
        env_prefix="PYLONTECH_WEB_",
        extra="ignore",
    )

    heatmap_deadband_mv: int = Field(default=2, ge=0)
    heatmap_scale_mv: int = Field(default=50, gt=0)
    cell_low_warning_mv: int = Field(default=3100, ge=0)
    cell_low_critical_mv: int = Field(default=3000, ge=0)
    cell_high_balancing_mv: int = Field(default=3547, ge=0)
    cell_high_warning_mv: int = Field(default=3600, ge=0)

    @model_validator(mode="after")
    def validate_ordering(self) -> "WebSettings":
        if self.heatmap_deadband_mv >= self.heatmap_scale_mv:
            raise ValueError(
                "heatmap deadband must be smaller than heatmap scale",
            )
        if not (
            self.cell_low_critical_mv
            < self.cell_low_warning_mv
            < self.cell_high_balancing_mv
            < self.cell_high_warning_mv
        ):
            raise ValueError(
                "cell thresholds must be ordered low critical, low warning, "
                "high balancing, high warning",
            )
        return self


def load_web_settings() -> WebSettings:
    return WebSettings()


class MqttSettings(BaseSettings):
    """Validated MQTT publication settings."""

    model_config = SettingsConfigDict(
        env_prefix="PYLONTECH_MQTT_",
        extra="ignore",
    )

    enabled: bool = False
    host: str | None = None
    port: int = Field(default=1883, ge=1, le=65535)
    client_id: str = "pylontech-console"
    username: str | None = None
    password: str | None = None
    topic_prefix: str = "pylontech"
    keepalive_seconds: int = Field(default=60, ge=1, le=65535)
    connect_timeout_seconds: float = Field(default=5, gt=0)
    reconnect_min_seconds: int = Field(default=1, ge=1)
    reconnect_max_seconds: int = Field(default=60, ge=1)
    tls_enabled: bool = False
    tls_ca_file: Path | None = None
    tls_cert_file: Path | None = None
    tls_key_file: Path | None = None
    tls_insecure: bool = False

    @field_validator(
        "host",
        "username",
        "password",
        mode="before",
    )
    @classmethod
    def strip_optional_string(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped or None

    @field_validator(
        "tls_ca_file",
        "tls_cert_file",
        "tls_key_file",
        mode="before",
    )
    @classmethod
    def empty_path_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("client_id")
    @classmethod
    def validate_client_id(cls, value: str) -> str:
        value = value.strip()
        if not value or "\x00" in value or len(value.encode()) > 128:
            raise ValueError("MQTT client ID must be 1..128 UTF-8 bytes without NUL")
        return value

    @field_validator("topic_prefix")
    @classmethod
    def validate_topic_prefix(cls, value: str) -> str:
        value = value.strip()
        levels = value.split("/")
        if (
            not value
            or any(not level for level in levels)
            or any(character in value for character in ("+", "#", "\x00"))
            or len(value.encode()) > 256
        ):
            raise ValueError("invalid MQTT topic prefix")
        return value

    @field_validator(
        "connect_timeout_seconds",
    )
    @classmethod
    def finite_positive(cls, value: float) -> float:
        if not math.isfinite(value) or value <= 0:
            raise ValueError("MQTT timeout values must be finite and positive")
        return value

    @model_validator(mode="after")
    def validate_configuration(self) -> "MqttSettings":
        if self.enabled and not self.host:
            raise ValueError("MQTT host is required when MQTT is enabled")
        if self.password is not None and not self.username:
            raise ValueError("MQTT password requires a username")
        if self.reconnect_max_seconds < self.reconnect_min_seconds:
            raise ValueError("MQTT reconnect maximum must not be below minimum")
        tls_values = (
            self.tls_ca_file,
            self.tls_cert_file,
            self.tls_key_file,
        )
        if not self.tls_enabled and (any(tls_values) or self.tls_insecure):
            raise ValueError("MQTT TLS options require TLS to be enabled")
        if (self.tls_cert_file is None) != (self.tls_key_file is None):
            raise ValueError("MQTT TLS certificate and key must be configured together")
        if self.tls_enabled:
            for path in tls_values:
                if path is not None and not path.is_file():
                    raise ValueError(f"MQTT TLS file is not readable: {path}")
        return self


def load_mqtt_settings() -> MqttSettings:
    return MqttSettings()
