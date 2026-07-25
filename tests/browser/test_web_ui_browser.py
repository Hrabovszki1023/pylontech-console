import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn
from playwright.sync_api import Page, ViewportSize, sync_playwright

from tests.web_fixture import create_web_test_app


@pytest.fixture(scope="module")
def live_web_url() -> Iterator[str]:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            create_web_test_app(
                first_module_voltages=(
                    3000,
                    3001,
                    3100,
                    3101,
                    3546,
                    3547,
                    3599,
                    3600,
                    3300,
                    3300,
                    3300,
                    3300,
                    3300,
                    3300,
                    3300,
                ),
            ),
            host="127.0.0.1",
            port=port,
            log_level="error",
            lifespan="off",
        ),
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    if not server.started:
        pytest.fail("browser test server did not start")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def _assert_page(page: Page, url: str, viewport: ViewportSize) -> None:
    page.set_viewport_size(viewport)
    page.goto(url, wait_until="networkidle")
    assert page.get_by_role("heading", name="Cell-voltage heatmap").is_visible()
    assert page.locator(".heat-cell").count() == 30
    assert page.locator(".absolute-critical").count() == 1
    assert page.locator(".absolute-low-warning").count() == 2
    assert page.locator(".absolute-balancing").count() == 2
    assert page.locator(".absolute-high-warning").count() == 1
    assert page.get_by_label("Absolute cell-voltage states").is_visible()
    assert page.locator("body").evaluate(
        "(body) => body.scrollWidth <= window.innerWidth",
    )
    page.get_by_role("link", name="MODULE-A").first.click()
    assert page.get_by_role("heading", name="MODULE-A").is_visible()
    assert page.locator(".data-table tbody tr").count() == 15


def test_desktop_and_narrow_viewports(live_web_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            _assert_page(
                page,
                live_web_url,
                {"width": 1440, "height": 900},
            )
            page.goto(live_web_url)
            _assert_page(
                page,
                live_web_url,
                {"width": 390, "height": 844},
            )
        finally:
            browser.close()
