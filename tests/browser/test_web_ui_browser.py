import socket
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, replace
from types import MappingProxyType

import pytest
import uvicorn
from playwright.sync_api import Page, ViewportSize, sync_playwright

from pylontech_console.domain.current_state import readonly_modules
from pylontech_console.polling import CurrentStateStore
from tests.web_fixture import create_web_test_app


@dataclass(frozen=True)
class LiveWeb:
    url: str
    store: CurrentStateStore


@pytest.fixture
def live_web() -> Iterator[LiveWeb]:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    app = create_web_test_app(
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
    )
    server = uvicorn.Server(
        uvicorn.Config(
            app,
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
        yield LiveWeb(
            url=f"http://127.0.0.1:{port}",
            store=app.state.current_state_store,
        )
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def _assert_page(page: Page, url: str, viewport: ViewportSize) -> None:
    page.set_viewport_size(viewport)
    page.goto(url, wait_until="networkidle")
    assert page.get_by_text("MQTT DISABLED", exact=True).is_visible()
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


def test_desktop_and_narrow_viewports(live_web: LiveWeb) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            _assert_page(
                page,
                live_web.url,
                {"width": 1440, "height": 900},
            )
            page.goto(live_web.url)
            _assert_page(
                page,
                live_web.url,
                {"width": 390, "height": 844},
            )
        finally:
            browser.close()


def _dispatch_refresh(page: Page) -> None:
    page.locator("body").dispatch_event("htmx:afterSwap")


def _set_first_cell_voltage(
    store: CurrentStateStore,
    voltage_mv: int,
    *,
    position: int | None = None,
) -> None:
    state = store.get()
    module = state.modules["MODULE-A"]
    assert module.cells.value is not None
    group = module.cells.value
    cells = (
        replace(group.cells[0], voltage_mv=voltage_mv),
        *group.cells[1:],
    )
    modules = dict(state.modules)
    modules["MODULE-A"] = replace(
        module,
        cells=replace(
            module.cells,
            value=replace(group, cells=cells),
        ),
    )
    inventory = state.inventory
    inventory_freshness = state.inventory_freshness
    if position is not None:
        records = dict(inventory.modules)
        records["MODULE-A"] = replace(
            records["MODULE-A"],
            current_position=position,
        )
        positions = {
            current_position: barcode
            for current_position, barcode in inventory.positions.items()
            if barcode != "MODULE-A"
        }
        positions[position] = "MODULE-A"
        inventory = replace(
            inventory,
            positions=MappingProxyType(positions),
            modules=MappingProxyType(records),
        )
        inventory_freshness = replace(
            inventory_freshness,
            value=inventory,
        )
    store.publish(
        replace(
            state,
            inventory=inventory,
            inventory_freshness=inventory_freshness,
            modules=readonly_modules(modules),
        ),
    )


def _htmx_refresh(page: Page, url: str) -> None:
    with page.expect_response(
        lambda response: response.url.endswith(
            "/web/fragments/overview",
        ),
    ):
        page.evaluate(
            """url => htmx.ajax("GET", `${url}/web/fragments/overview`, {
                target: "#rack-content",
                swap: "innerHTML",
            })""",
            url,
        )


def test_changed_cell_voltage_flashes_and_restarts_timer(
    live_web: LiveWeb,
) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(live_web.url, wait_until="networkidle")
            voltage = page.locator(
                '[data-cell-voltage-key="MODULE-A:0"]',
            )
            tile = voltage.locator("xpath=..")
            deviation = tile.locator("small").first

            assert not voltage.evaluate(
                "(element) => element.classList.contains("
                "'cell-voltage-changed')",
            )
            _dispatch_refresh(page)
            assert not voltage.evaluate(
                "(element) => element.classList.contains("
                "'cell-voltage-changed')",
            )

            initial_voltage = int(
                voltage.get_attribute("data-cell-voltage-mv") or "0",
            )
            _set_first_cell_voltage(
                live_web.store,
                initial_voltage + 1,
                position=9,
            )
            _htmx_refresh(page, live_web.url)
            voltage = page.locator(
                '[data-cell-voltage-key="MODULE-A:0"]',
            )
            tile = voltage.locator("xpath=..")
            deviation = tile.locator("small").first
            assert tile.locator("xpath=../th/span").text_content() == (
                "Position 9"
            )

            assert voltage.evaluate(
                "(element) => element.classList.contains("
                "'cell-voltage-changed')",
            )
            assert voltage.evaluate(
                "(element) => getComputedStyle(element).color",
            ) == "rgb(0, 138, 59)"
            assert page.locator(".cell-voltage-changed").count() == 1
            assert "cell-voltage-changed" not in (
                tile.get_attribute("class") or ""
            )
            assert not deviation.evaluate(
                "(element) => element.classList.contains("
                "'cell-voltage-changed')",
            )

            page.wait_for_timeout(500)
            _set_first_cell_voltage(live_web.store, initial_voltage + 2)
            _htmx_refresh(page, live_web.url)
            voltage = page.locator(
                '[data-cell-voltage-key="MODULE-A:0"]',
            )
            latest_tile = voltage.locator("xpath=..")
            latest_background = latest_tile.get_attribute("style")
            latest_deviation = latest_tile.locator(
                "small",
            ).first.text_content()
            page.wait_for_timeout(2600)
            assert voltage.evaluate(
                "(element) => element.classList.contains("
                "'cell-voltage-changed')",
            )
            page.wait_for_timeout(500)
            assert not voltage.evaluate(
                "(element) => element.classList.contains("
                "'cell-voltage-changed')",
            )
            tile = voltage.locator("xpath=..")
            assert tile.get_attribute("style") == latest_background
            assert tile.locator("small").first.text_content() == (
                latest_deviation
            )
        finally:
            browser.close()


def test_unavailable_transition_and_first_reappearance_do_not_flash(
    live_web: LiveWeb,
) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.goto(live_web.url, wait_until="networkidle")
            voltage = page.locator("[data-cell-voltage-key]").first
            key = voltage.get_attribute("data-cell-voltage-key")
            original = int(
                voltage.get_attribute("data-cell-voltage-mv") or "0",
            )

            voltage.evaluate(
                """element => {
                    delete element.dataset.cellVoltageKey;
                    delete element.dataset.cellVoltageMv;
                    element.textContent = "N/A";
                }""",
            )
            _dispatch_refresh(page)
            assert page.locator(".cell-voltage-changed").count() == 0

            voltage.evaluate(
                """(element, values) => {
                    element.dataset.cellVoltageKey = values.key;
                    element.dataset.cellVoltageMv = String(values.voltage);
                    element.textContent = String(values.voltage);
                }""",
                {"key": key, "voltage": original + 10},
            )
            _dispatch_refresh(page)
            assert page.locator(".cell-voltage-changed").count() == 0
        finally:
            browser.close()
