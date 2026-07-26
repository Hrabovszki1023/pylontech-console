from fastapi.testclient import TestClient
import re
import pytest

from pylontech_console.config import WebSettings
from pylontech_console.mqtt_health import (
    MqttConnectionState,
    MqttHealth,
)
from pylontech_console.outputs.web.query import _cell_color
from pylontech_console.outputs.web.routes import encode_test_id_component
from tests.web_fixture import RECEIVED_TIME, create_web_test_app


def _test_ids(html: str) -> list[str]:
    return re.findall(r'data-testid="([^"]+)"', html)


def test_rack_overview_renders_module_heatmap_and_local_htmx() -> None:
    client = TestClient(create_web_test_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Rack SOC" in response.text
    assert "Cell-voltage heatmap" in response.text
    assert "Module voltage" in response.text
    assert "Module cell average" in response.text
    assert "Cell 0" in response.text
    assert "Cell 14" in response.text
    assert response.text.count(
        'class="heat-cell heat-cell-current absolute-normal"',
    ) == 30
    assert "3330" in response.text
    assert 'src="http://testserver/assets/htmx.min.js"' in response.text
    assert 'src="http://testserver/assets/app.js"' in response.text
    assert 'hx-trigger="every 5s"' in response.text
    assert response.text.count("data-cell-voltage-key=") == 30
    assert "cell-voltage-changed" not in response.text
    assert "https://unpkg.com" not in response.text
    assert client.get("/assets/app.js").status_code == 200
    assert "MQTT DISABLED" in " ".join(response.text.split())


def test_gui_test_id_registry_is_unique_and_shared_with_fragments() -> None:
    client = TestClient(create_web_test_app())
    rack_page = client.get("/").text
    rack_fragment = client.get("/web/fragments/overview").text
    module_page = client.get("/modules/MODULE-A").text
    module_fragment = client.get(
        "/web/fragments/modules/MODULE-A",
    ).text

    for html in (rack_page, rack_fragment, module_page, module_fragment):
        ids = _test_ids(html)
        assert ids
        assert len(ids) == len(set(ids))
        assert all(re.fullmatch(r"[A-Za-z0-9._%-]+", value) for value in ids)

    assert set(_test_ids(rack_page)) == set(_test_ids(rack_fragment)) | {
        "rack-page",
    }
    assert set(_test_ids(module_page)) == set(_test_ids(module_fragment)) | {
        "module-MODULE-A-page",
    }
    assert {
        f"module-MODULE-A-cell-{index}-heatmap"
        for index in range(15)
    } <= set(_test_ids(rack_page))
    assert {
        f"module-MODULE-A-cell-{index}-row"
        for index in range(15)
    } <= set(_test_ids(module_page))


def test_test_id_barcode_encoding_is_reversible_and_collision_free() -> None:
    assert encode_test_id_component("ABC-_.123") == "ABC-_.123"
    assert encode_test_id_component("A/B% +#") == "A%2FB%25%20%2B%23"
    assert encode_test_id_component("ä") == "%C3%A4"
    assert encode_test_id_component("A/B") != encode_test_id_component("A%2FB")

    client = TestClient(
        create_web_test_app(unsafe_barcode='<x/" onmouseover="secret">'),
    )
    html = client.get("/").text

    assert "module-%3Cx%2F%22%20onmouseover%3D%22secret%22%3E-card" in (
        _test_ids(html)
    )


def test_heatmap_uses_independent_module_averages_and_fixed_deadband() -> None:
    client = TestClient(create_web_test_app())

    response = client.get("/")

    assert response.status_code == 200
    assert response.text.count("<strong>3330.00</strong>") == 1
    assert response.text.count("<strong>3331.00</strong>") == 1
    assert 'data-deviation="-1.0000"' in response.text
    assert 'data-deviation="0.0000"' in response.text
    assert 'data-deviation="1.0000"' in response.text
    assert response.text.count("background-color: #ffffff") == 30
    assert "−50 mV" in response.text
    assert "±2 mV neutral" in response.text
    assert "+50 mV" in response.text


def test_heatmap_color_has_fixed_deadband_and_endpoint_saturation() -> None:
    assert _cell_color(-2, 2, 50) == ("#ffffff", "#172033")
    assert _cell_color(2, 2, 50) == ("#ffffff", "#172033")
    assert _cell_color(-50, 2, 50)[0] == "rgb(37, 99, 235)"
    assert _cell_color(-100, 2, 50)[0] == "rgb(37, 99, 235)"
    assert _cell_color(50, 2, 50)[0] == "rgb(220, 58, 58)"
    assert _cell_color(100, 2, 50)[0] == "rgb(220, 58, 58)"
    assert _cell_color(-3, 2, 50)[0] not in {
        "#ffffff",
        "rgb(37, 99, 235)",
    }
    assert _cell_color(3, 2, 50)[0] not in {
        "#ffffff",
        "rgb(220, 58, 58)",
    }


def test_absolute_voltage_boundaries_and_bms_precedence() -> None:
    voltages = (
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
    )
    statuses = (
        "Normal",
        "Normal",
        "Normal",
        "Normal",
        "Normal",
        "Normal",
        "Normal",
        "Normal",
        "Alarm",
        "Normal",
        "Normal",
        "Normal",
        "Normal",
        "Normal",
        "Normal",
    )
    client = TestClient(
        create_web_test_app(
            first_module_voltages=voltages,
            first_voltage_statuses=statuses,
        ),
    )

    response = client.get("/")

    assert response.status_code == 200
    assert 'data-cell-index="0"' in response.text
    assert 'data-absolute-state="critical"' in response.text
    assert 'data-absolute-state="low-warning"' in response.text
    assert 'data-absolute-state="balancing"' in response.text
    assert 'data-absolute-state="high-warning"' in response.text
    assert "Low critical" in response.text
    assert "Low warning" in response.text
    assert "Charge/balancing" in response.text
    assert "High warning" in response.text
    assert "BMS critical: Alarm" in response.text
    assert "absolute-critical" in response.text
    assert "absolute-low-warning" in response.text
    assert "absolute-balancing" in response.text
    assert "absolute-high-warning" in response.text
    expected_states = {
        0: "critical",
        1: "low-warning",
        2: "low-warning",
        3: "normal",
        4: "normal",
        5: "balancing",
        6: "balancing",
        7: "high-warning",
        8: "critical",
    }
    for index, absolute_state in expected_states.items():
        assert re.search(
            rf'data-cell-index="{index}"[^>]+'
            rf'data-absolute-state="{absolute_state}"',
            response.text,
        )


def test_web_settings_override_legend_and_absolute_thresholds() -> None:
    settings = WebSettings(
        heatmap_deadband_mv=3,
        heatmap_scale_mv=60,
        cell_low_critical_mv=3010,
        cell_low_warning_mv=3110,
        cell_high_balancing_mv=3550,
        cell_high_warning_mv=3610,
    )
    client = TestClient(
        create_web_test_app(
            first_module_voltages=(3550,) * 15,
            web_settings=settings,
        ),
    )

    response = client.get("/")

    assert response.status_code == 200
    assert "−60 mV" in response.text
    assert "±3 mV neutral" in response.text
    assert "Charge/balancing ≥3550 mV" in response.text
    assert "Low ≤3110 · high ≥3610 mV" in response.text
    assert response.text.count(
        'data-absolute-state="balancing"',
    ) == 15


def test_stale_capture_is_neutral_and_excluded_from_module_average() -> None:
    client = TestClient(create_web_test_app(stale_second_module=True))

    response = client.get("/")

    assert response.status_code == 200
    assert (
        'data-testid="module-MODULE-B-heatmap-status">stale</small>'
        in response.text
    )
    assert response.text.count(
        'class="heat-cell heat-cell-stale absolute-stale"',
    ) == 15
    assert response.text.count("data-cell-voltage-key=") == 15
    assert response.text.count("<strong>3330.00</strong>") == 1
    assert "<strong>3331.00</strong>" not in response.text


def test_module_detail_renders_all_cells_and_stable_barcode_route() -> None:
    client = TestClient(create_web_test_app())

    response = client.get("/modules/MODULE-A")

    assert response.status_code == 200
    assert "MODULE-A" in response.text
    assert "15/15" in response.text
    assert response.text.count("<th scope=\"row\">Cell ") == 15
    assert "24500 mAh" in response.text
    assert client.get("/modules/UNKNOWN").status_code == 404


def test_device_values_are_html_escaped() -> None:
    client = TestClient(
        create_web_test_app(unsafe_barcode="<script>alert(1)</script>"),
    )

    response = client.get("/")

    assert response.status_code == 200
    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.text


def test_fragments_render_without_duplicate_document_shell() -> None:
    client = TestClient(create_web_test_app())

    rack = client.get("/web/fragments/overview")
    module = client.get("/web/fragments/modules/MODULE-A")

    assert rack.status_code == 200
    assert module.status_code == 200
    assert "<!doctype html>" not in rack.text.lower()
    assert "<!doctype html>" not in module.text.lower()
    assert "Cell-voltage heatmap" in rack.text
    assert "All cell measurements" in module.text


def test_web_adapter_adds_no_write_or_command_routes() -> None:
    client = TestClient(create_web_test_app())

    assert client.post("/").status_code == 405
    assert client.get("/commands").status_code == 404
    assert client.post("/modules/MODULE-A").status_code == 405


@pytest.mark.parametrize(
    ("state", "label"),
    [
        (MqttConnectionState.DISABLED, "MQTT DISABLED"),
        (MqttConnectionState.CONNECTING, "MQTT CONNECTING"),
        (MqttConnectionState.CONNECTED, "MQTT ONLINE"),
        (MqttConnectionState.DISCONNECTED, "MQTT OFFLINE"),
    ],
)
def test_mqtt_status_badges_are_read_only(
    state: MqttConnectionState,
    label: str,
) -> None:
    connected = state is MqttConnectionState.CONNECTED
    client = TestClient(
        create_web_test_app(
            mqtt_health=MqttHealth(
                enabled=state is not MqttConnectionState.DISABLED,
                state=state,
                connected=connected,
                last_connected_at=(
                    RECEIVED_TIME if connected else None
                ),
                consecutive_failures=(
                    1 if state is MqttConnectionState.DISCONNECTED else 0
                ),
                error=(
                    "MQTT broker unavailable"
                    if state is MqttConnectionState.DISCONNECTED
                    else None
                ),
            ),
        ),
    )

    response = client.get("/")

    assert label in " ".join(response.text.split())
    if state is MqttConnectionState.DISCONNECTED:
        assert "MQTT broker unavailable" in response.text
    assert 'type="password"' not in response.text
    assert "MQTT enable" not in response.text
    assert client.post("/mqtt").status_code == 404
