from fastapi.testclient import TestClient

from tests.web_fixture import create_web_test_app


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
    assert response.text.count('class="heat-cell heat-cell-current"') == 30
    assert "3330" in response.text
    assert 'src="http://testserver/assets/htmx.min.js"' in response.text
    assert 'hx-trigger="every 5s"' in response.text
    assert "https://unpkg.com" not in response.text


def test_heatmap_uses_independent_module_averages_and_symmetric_signs() -> None:
    client = TestClient(create_web_test_app())

    response = client.get("/")

    assert response.status_code == 200
    assert response.text.count("<strong>3330.00</strong>") == 1
    assert response.text.count("<strong>3331.00</strong>") == 1
    assert 'data-deviation="-1.0000"' in response.text
    assert 'data-deviation="0.0000"' in response.text
    assert 'data-deviation="1.0000"' in response.text
    assert "rgb(37, 99, 235)" in response.text
    assert "rgb(220, 58, 58)" in response.text
    assert "background-color: #ffffff" in response.text


def test_stale_capture_is_neutral_and_excluded_from_module_average() -> None:
    client = TestClient(create_web_test_app(stale_second_module=True))

    response = client.get("/")

    assert response.status_code == 200
    assert 'class="row-status row-status-stale">stale</small>' in response.text
    assert response.text.count('class="heat-cell heat-cell-stale"') == 15
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
