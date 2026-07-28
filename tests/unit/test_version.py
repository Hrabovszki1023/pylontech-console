import pytest

from pylontech_console.version import (
    DEVELOPMENT_REVISION,
    PUBLIC_VERSION,
    load_build_identity,
    validate_release_tag,
)

REVISION = "fc830cd8ff0e2ebcde20094a91709a87ef8b713b"


def test_local_identity_has_explicit_development_revision() -> None:
    identity = load_build_identity({})

    assert identity.version == PUBLIC_VERSION
    assert identity.revision == DEVELOPMENT_REVISION
    assert identity.short_revision == DEVELOPMENT_REVISION


def test_ci_identity_uses_full_revision_and_short_web_form() -> None:
    identity = load_build_identity(
        {
            "PYLONTECH_BUILD_VERSION": PUBLIC_VERSION,
            "PYLONTECH_BUILD_REVISION": REVISION,
        },
    )

    assert identity.revision == REVISION
    assert identity.short_revision == "fc830cd"


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        (
            {"PYLONTECH_BUILD_VERSION": "0.1.0-beta.2"},
            "does not match",
        ),
        (
            {"PYLONTECH_BUILD_REVISION": "fc830cd"},
            "full lowercase Git SHA",
        ),
    ],
)
def test_invalid_injected_identity_fails_closed(
    environment: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        load_build_identity(environment)


def test_matching_release_tag_is_accepted() -> None:
    validate_release_tag("tag", f"v{PUBLIC_VERSION}")
    validate_release_tag("branch", "main")


@pytest.mark.parametrize(
    "tag",
    [
        "v0.1.0-beta.2",
        "0.1.0-beta.1",
        "vv0.1.0-beta.1",
    ],
)
def test_mismatching_release_tag_fails_before_publish(tag: str) -> None:
    with pytest.raises(ValueError, match="does not match public version"):
        validate_release_tag("tag", tag)
