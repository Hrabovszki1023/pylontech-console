import math
from typing import Annotated

from pydantic import (
    Field,
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
