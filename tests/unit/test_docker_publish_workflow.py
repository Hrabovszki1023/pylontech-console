from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parents[2]
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "docker-publish.yml"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_docker_publish_workflow_is_valid_yaml() -> None:
    document = yaml.safe_load(workflow_text())

    assert document["name"] == "Verify and publish Docker image"
    assert document["permissions"] == {"contents": "read"}
    assert set(document["jobs"]) == {"verify", "image", "dockerhub-description"}


def test_docker_publish_workflow_has_safe_events_and_credentials() -> None:
    text = workflow_text()

    assert "pull_request:" in text
    assert "branches:\n      - main" in text
    assert '"v*.*.*"' in text
    assert "if: github.event_name == 'push'" in text
    assert "push: ${{ github.event_name == 'push' }}" in text
    assert "${{ secrets.DOCKERHUB_USERNAME }}" in text
    assert "${{ secrets.DOCKERHUB_TOKEN }}" in text
    assert "hrabovszki/pylontech-console" in text
    assert "platforms: linux/amd64" in text
    assert "Update Docker Hub overview" in text
    assert "enable-url-completion: true" in text


def test_docker_publish_workflow_reserves_latest_for_stable_tags() -> None:
    text = workflow_text()

    assert "type=raw,value=main" in text
    assert "type=sha,prefix=sha-,format=short" in text
    assert "type=semver,pattern={{version}}" in text
    assert (
        "type=raw,value=latest,enable=${{ startsWith(github.ref, "
        "'refs/tags/v') && !contains(github.ref, '-') }}"
    ) in text
    assert "image:\n    name:" in text
    assert "needs: verify" in text


def test_workflow_injects_and_labels_exact_build_identity() -> None:
    text = workflow_text()

    assert "validate_release_tag" in text
    assert "PYLONTECH_BUILD_VERSION=${{ needs.verify.outputs.public-version }}" in text
    assert "PYLONTECH_BUILD_REVISION=${{ github.sha }}" in text
    assert (
        "org.opencontainers.image.version="
        "${{ needs.verify.outputs.public-version }}"
    ) in text
    assert "org.opencontainers.image.revision=${{ github.sha }}" in text
    assert "org.opencontainers.image.source=${{ github.server_url }}" in text


def test_actions_are_pinned_to_commit_shas() -> None:
    for line in workflow_text().splitlines():
        stripped = line.strip()
        if not stripped.startswith("uses:"):
            continue
        reference = stripped.split("@", maxsplit=1)[1].split()[0]
        assert len(reference) == 40
        assert all(character in "0123456789abcdef" for character in reference)
