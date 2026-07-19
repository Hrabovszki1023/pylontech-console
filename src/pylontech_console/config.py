import math
from typing import Annotated

from pydantic import Field, StringConstraints, field_validator
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
