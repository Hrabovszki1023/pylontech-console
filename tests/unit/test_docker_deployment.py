from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parents[2]


def test_public_compose_uses_published_image_and_secret() -> None:
    document = yaml.safe_load(
        (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8"),
    )
    service = document["services"]["pylontech-console"]

    assert service["image"] == (
        "hrabovszki/pylontech-console:${PYLONTECH_IMAGE_TAG:-main}"
    )
    assert "build" not in service
    assert service["restart"] == "unless-stopped"
    assert service["ports"] == ["${PYLONTECH_HTTP_PUBLISHED_PORT:-8001}:8000"]
    assert service["environment"]["PYLONTECH_HTTP_PORT"] == 8000
    assert service["environment"]["PYLONTECH_MQTT_ENABLED"] == (
        "${PYLONTECH_MQTT_ENABLED:-false}"
    )
    assert service["environment"]["PYLONTECH_CONSOLE_LOGIN_PASSWORD_FILE"] == (
        "/run/secrets/pylontech_console_password"
    )
    assert service["secrets"] == ["pylontech_console_password"]


def test_development_compose_restores_local_build() -> None:
    document = yaml.safe_load(
        (PROJECT_ROOT / "docker-compose.dev.yml").read_text(encoding="utf-8"),
    )
    service = document["services"]["pylontech-console"]

    assert service["image"] == "pylontech-console:development"
    assert service["build"]["context"] == "."


def test_image_has_non_root_runtime_and_http_healthcheck() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "USER pylontech" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "/api/v1/health" in dockerfile


def test_public_environment_example_contains_no_password() -> None:
    example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")

    assert "PYLONTECH_WAVESHARE_HOST=" in example
    assert "PYLONTECH_HTTP_PUBLISHED_PORT=8001" in example
    assert "PYLONTECH_MQTT_ENABLED=false" in example
    assert "PYLONTECH_CONSOLE_LOGIN_PASSWORD=" not in example


def test_docker_build_context_excludes_local_secrets() -> None:
    dockerignore = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert ".env" in dockerignore.splitlines()
    assert "secrets" in dockerignore.splitlines()


def test_readme_documents_public_lifecycle() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    assert "cp .env.example .env" in readme
    assert "docker compose pull" in readme
    assert "docker compose up -d" in readme
    assert "docker compose down" in readme
