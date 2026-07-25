# Web UI contract version 0.1

## Status

Accepted for implementation by GitHub issue #21.

This document refines the web-interface requirements in `version-0.1.md`. If
the two documents conflict, implementation must stop until the conflict is
resolved explicitly.

## Purpose and boundaries

The read-only web UI exposes the authoritative shared `CurrentStateStore`
through the query/view-model layer shared with the REST API.

```text
CurrentStateStore
        |
shared query/view models
        +-- REST API -> JSON
        `-- Web UI -> Jinja2/HTMX -> HTML
```

REST and web must use identical value, unit, ordering, derived-value,
validity, age and staleness rules. The web adapter must not query the
Waveshare gateway, execute console commands, start polling, parse protocol
responses or maintain a duplicate current-state model.

The UI must not provide write operations, configuration changes or arbitrary
console commands.

## Technology and delivery

- Pages are rendered on the server with Jinja2.
- HTMX provides periodic read-only fragment refreshes and enhanced navigation.
- The UI remains useful without JavaScript.
- Required static assets are served by the application; normal operation on
  the local network must not require a public CDN.
- Web implementation belongs under
  `src/pylontech_console/outputs/web/`.
- Existing REST and OpenAPI routes remain unchanged.

## Pages

### Rack overview

`GET /` displays:

- service and connection status;
- sanitized current errors;
- last successful acquisition and data ages;
- detected and present module count;
- rack voltage, current, derived power, SOC and SOH;
- highest, average and lowest cell voltage;
- rack-wide cell-voltage delta;
- highest, average and lowest temperature;
- recommended charge and discharge voltage/current limits;
- current position-to-barcode topology;
- the cell-voltage heatmap defined below.

### Module detail

`GET /modules/{barcode}` uses the stable barcode in navigation and URLs.

It displays:

- barcode, current position and presence state;
- model, firmware and board identity;
- voltage, current, temperature, SOC and module state;
- minimum and maximum cell voltage and their delta;
- the complete current cell table;
- cell voltage, current, temperature, SOC, coulomb value, balancing state and
  modeled statuses;
- data age, validity, staleness and sanitized acquisition errors.

An unknown barcode returns HTTP 404. A known module with unavailable, invalid
or stale measurements remains accessible and shows explicit status metadata.

## Cell-voltage heatmap

The heatmap follows a matrix layout comparable to a financial monthly-return
heatmap.

### Matrix structure

- Rows represent currently present modules in ascending rack-position order.
- Row labels show the current position and stable barcode.
- Columns represent cells in ascending zero-based data order.
- Human-facing headings use `Cell 1` through `Cell N`.
- Every available cell tile displays its measured voltage numerically in mV.
- Signed deviation may be shown as secondary visible text or accessible text.
- No value may be available only through a tooltip.
- The heatmap uses horizontal scrolling on narrow screens without changing row
  or cell order.

### Reference values

The UI displays these values separately above the heatmap:

- `Rack SOC`: the authoritative rack `soc_percent` measurement;
- `Average cell voltage`: the arithmetic mean in mV of all valid, non-stale
  cell measurements included in the heatmap.

Average cell voltage is a derived voltage reference. It must not be presented
as the SOC measurement.

For `n` included cells:

```text
average_cell_voltage_mv =
    sum(cell.voltage_mv for included cells) / n
```

The displayed average may be rounded for presentation, but deviation and
color calculations use the unrounded response-snapshot value.

### Deviation

For every included cell:

```text
deviation_mv = cell.voltage_mv - average_cell_voltage_mv
```

The heatmap uses a symmetric diverging blue-white-red scale centered at zero:

- a deviation of exactly `0 mV` is white;
- a negative deviation is blue;
- a positive deviation is red;
- color intensity increases with the absolute deviation;
- negative and positive colors use the same magnitude scale;
- the scale limit for one rendered snapshot is the greatest absolute
  deviation among included cells;
- when every deviation is zero, all included cells use the neutral white
  treatment and the scale remains mathematically safe;
- a visible legend shows the current negative, zero and positive limits in mV.

The concrete color interpolation may vary, but the sign, center, symmetry,
ordering and status behavior are contractual.

### Status and accessibility

Color must never be the only carrier of value or status.

- Numeric voltage remains visible in every available tile.
- Text contrast remains readable throughout the color scale.
- Semantic or accessible text identifies voltage, signed deviation and status.
- Keyboard and screen-reader navigation retain meaningful module and cell
  labels.
- Status badges/text distinguish current, stale, invalid and unavailable data.
- Unavailable cells display `N/A`, never a fabricated numeric zero.

### Invalid, unavailable and stale values

- Only valid, non-stale cell groups contribute to the average and color scale.
- Retained stale or invalid values may be displayed only for diagnostics and
  must be explicitly marked as stale or invalid.
- Stale and invalid values do not contribute to the average or color scale.
- Invalid, stale and unavailable tiles use a neutral treatment outside the
  blue-white-red measurement scale.
- If no valid current cells exist, the UI shows no calculated average, uses
  neutral tiles and displays a clear unavailable-state message.

## Refresh behavior

- Current-state sections refresh through HTMX without a full-page reload.
- The default refresh interval is 5 seconds.
- One timezone-aware UTC `generated_at` snapshot is used for every age and
  staleness calculation in one rendered page or fragment response.
- A refresh failure leaves the last successfully rendered page visible.
- The next successful response clearly communicates the current service,
  acquisition and freshness state.
- Full-page navigation and refresh remain functional without HTMX.

## Ordering and formatting

- Present modules are ordered by current position.
- Stable barcodes are used for module links and identity.
- Cell measurements retain their parser-provided zero-based order internally.
- Human-facing cell numbers are one-based labels only.
- Units remain explicit.
- Unavailable values are not converted to zero.
- Device states and unknown enum values remain visible strings.
- `raw_payload` is never rendered.
- Device-provided values and error details are HTML-escaped.

## Testing

Tests use controlled `CurrentStateStore` snapshots and a fixed clock. They
must verify:

- rack overview rendering and required values;
- every discovered module appears in position order;
- module links and lookup use stable barcodes;
- unknown-module HTTP 404 behavior;
- every modeled cell appears and every available heatmap tile contains its
  numeric voltage;
- average cell-voltage calculation;
- exact-zero deviation uses the neutral class;
- positive deviation uses the red side and negative deviation the blue side;
- symmetric scaling and the all-equal safe case;
- invalid and stale groups are excluded from the reference mean;
- invalid, stale and unavailable values are visibly marked;
- unavailable values render as `N/A`, never zero;
- stale values are not presented as current;
- status remains understandable without color;
- Jinja2 escaping prevents device values or errors from becoming markup;
- HTMX fragments use the same query/view-model layer as full pages and REST;
- web requests execute no console commands and start no polling;
- no write or arbitrary-command routes are introduced;
- existing REST behavior and tests remain unchanged;
- desktop and narrow-viewport browser rendering.

## Verification

```text
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m mypy src tests
python -m pylontech_console.main
docker build -t pylontech-console .
docker compose config
```

Long-running local and Docker commands are verified with controlled
start/request/termination checks. On the Proxmox Docker host, verify:

```text
GET /
GET /modules/{known-barcode}
GET /api/v1/health
GET /api/v1/modules
```

The five-module, 75-cell live rack is used for visual verification at desktop
and narrow viewport sizes.

## Out of scope

- MQTT publication;
- SQLite persistence;
- historical measurements, charts or trends;
- a temperature heatmap as a required deliverable;
- authentication and authorization;
- configuration editing;
- per-cell pages;
- write operations;
- arbitrary console commands;
- independent polling, parsing or discovery;
- changes to the REST response contract.
