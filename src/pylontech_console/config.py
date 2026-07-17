from typing import Annotated

from pydantic import Field, StringConstraints
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
    response_timeout_seconds: float = Field(default=3, gt=0)


def load_waveshare_settings() -> WaveshareSettings:
    """Load Waveshare settings from the process environment."""

    return WaveshareSettings()  # type: ignore[call-arg]
