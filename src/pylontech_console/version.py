import os
import re
from collections.abc import Mapping
from dataclasses import dataclass

APPLICATION_NAME = "pylontech-console"
DISPLAY_NAME = "Pylontech Console"
__version__ = "0.1.0-beta.1"
PUBLIC_VERSION = __version__
DEVELOPMENT_REVISION = "development"
BUILD_VERSION_ENV = "PYLONTECH_BUILD_VERSION"
BUILD_REVISION_ENV = "PYLONTECH_BUILD_REVISION"
FULL_GIT_SHA = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class BuildIdentity:
    name: str
    display_name: str
    version: str
    revision: str

    @property
    def short_revision(self) -> str:
        if self.revision == DEVELOPMENT_REVISION:
            return self.revision
        return self.revision[:7]


def load_build_identity(
    environment: Mapping[str, str] | None = None,
) -> BuildIdentity:
    values = os.environ if environment is None else environment
    injected_version = values.get(BUILD_VERSION_ENV, "").strip()
    if injected_version and injected_version != PUBLIC_VERSION:
        raise ValueError(
            "injected build version does not match public version",
        )
    revision = values.get(
        BUILD_REVISION_ENV,
        DEVELOPMENT_REVISION,
    ).strip()
    if revision != DEVELOPMENT_REVISION and FULL_GIT_SHA.fullmatch(revision) is None:
        raise ValueError(
            "build revision must be a full lowercase Git SHA or development",
        )
    return BuildIdentity(
        name=APPLICATION_NAME,
        display_name=DISPLAY_NAME,
        version=PUBLIC_VERSION,
        revision=revision,
    )


def validate_release_tag(ref_type: str, ref_name: str) -> None:
    if ref_type != "tag":
        return
    if not ref_name.startswith("v") or ref_name[1:] != PUBLIC_VERSION:
        raise ValueError(
            f"Git tag {ref_name} does not match public version "
            f"{PUBLIC_VERSION}",
        )
