# Web UI contract version 0.1

## Status

Accepted for implementation by GitHub issue #21. The cell-voltage
visualization requirements are refined by GitHub issues #27 and #30. MQTT
status requirements are refined by GitHub issue #33.

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
- MQTT status as `MQTT DISABLED`, `MQTT CONNECTING`, `MQTT ONLINE` or
  `MQTT OFFLINE`, plus available connection timestamps, failure count and
  sanitized error;
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

The rack overview is also the module overview. It lists every currently known
module with its stable barcode, current position, presence, model, voltage,
current, SOC, basic state, cell-voltage minimum/maximum/delta, age, validity
and staleness. Each module links to its barcode-based detail page. Version 0.1
does not require a separate `GET /modules` overview page.

### MQTT status

The MQTT status on the rack overview is a read-only operational indicator. Its
authoritative state, labels, timestamps, failure count, error sanitization and
effect on combined service health are defined in `mqtt-v0.1.md`.

The badge always contains visible text, so color is not the only state
carrier. Full-page rendering and HTMX rack-fragment refreshes use the same
shared MQTT health query. MQTT broker credentials, TLS key material and
complete low-level network diagnostics are never rendered.

The web UI must not contain an MQTT enable switch, broker configuration,
credential fields, connect/disconnect action or any other MQTT write
operation. MQTT is configured exclusively through validated deployment
configuration.

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
- The first data column is `Module voltage` and shows the module-terminal
  `voltage_mv` measurement, approximately 48 V, with an explicit unit.
- The second data column is `Module cell average` and shows the derived
  arithmetic mean of that module's 15 valid current cell voltages in mV.
- The remaining 15 columns represent parser cell indices `0` through `14` in
  ascending order and are labeled `Cell 0` through `Cell 14`.
- Every available cell tile displays its measured voltage numerically in mV.
- Signed deviation may be shown as secondary visible text or accessible text.
- No value may be available only through a tooltip.
- The heatmap uses horizontal scrolling on narrow screens without changing row
  or cell order.

### Reference values

The UI displays these values separately above the heatmap:

- `Rack SOC`: the authoritative rack `soc_percent` measurement.

Each module row displays its own `Module cell average`. The console does not
provide a per-module `average_cell_voltage_mv`; this value is derived from the
15 cell voltages returned by `bat <position>`. The `average_cell_voltage_mv`
returned by `pwrsys` is a rack-level BMS value and remains a separate rack
overview measurement.

For module `m` with its 15 valid, non-stale cells:

```text
module_average_cell_voltage_mv[m] =
    sum(cell.voltage_mv for cell in module[m].cells) / 15
```

The module average is the zero reference for that module row. It must not be
presented as the rack SOC or as the rack-level BMS average. The displayed
average may be rounded for presentation, but deviation and color calculations
use the unrounded response-snapshot value.

### Deviation

For every valid current cell in module `m`:

```text
deviation_mv =
    cell.voltage_mv - module_average_cell_voltage_mv[m]
```

The heatmap uses a fixed symmetric diverging blue-white-red scale centered at
zero:

- deviations from `-2 mV` through `+2 mV`, inclusive, are white;
- a deviation below `-2 mV` is increasingly blue;
- a deviation above `+2 mV` is increasingly red;
- negative and positive colors use the same fixed `50 mV` magnitude scale;
- deviations at or beyond `-50 mV` and `+50 mV` use the respective full
  endpoint color;
- the scale and the meaning of a color do not change between refreshes;
- when every deviation is in the neutral deadband, all included cells use the
  neutral white treatment;
- a visible legend shows the fixed negative endpoint, neutral deadband and
  positive endpoint in mV.

The concrete color interpolation may vary, but the sign, center, symmetry,
ordering and status behavior are contractual.

### Absolute cell-voltage state

Relative deviation and absolute voltage answer different questions and use
independent visual channels:

- tile background communicates deviation from the module mean;
- a visible border plus text or icon communicates absolute voltage state;
- color alone is never the only absolute-state signal;
- relative background remains visible when an absolute-state border is
  present.

The default absolute thresholds are:

```text
low warning                 voltage <= 3100 mV
low critical                voltage <= 3000 mV
upper charge/balancing zone voltage >= 3547 mV
high warning                voltage >= 3600 mV
```

`3547 mV` is the integer-millivolt representation of the per-cell average at
the configured `53.2 V` module charge target (`53.2 V / 15`). It is an
informational upper charge/balancing state, not a claim that the cell has
crossed an internal Pylontech protection threshold.

Absolute-state precedence from highest to lowest is:

1. a modeled BMS cell `voltage_status` other than `Normal` is critical;
2. a voltage at or below the low-critical threshold is critical;
3. a voltage at or above the high-warning threshold is warning/high;
4. a voltage at or below the low-warning threshold is warning/low;
5. a voltage at or above the upper charge/balancing threshold is
   informational;
6. otherwise the absolute state is normal.

The BMS status always takes precedence over numeric UI thresholds. UI labels
must not present configurable thresholds as authoritative or internal BMS
protection limits.

### Visualization configuration

The following validated integer-millivolt environment settings are supported:

```text
PYLONTECH_WEB_HEATMAP_DEADBAND_MV=2
PYLONTECH_WEB_HEATMAP_SCALE_MV=50
PYLONTECH_WEB_CELL_LOW_WARNING_MV=3100
PYLONTECH_WEB_CELL_LOW_CRITICAL_MV=3000
PYLONTECH_WEB_CELL_HIGH_BALANCING_MV=3547
PYLONTECH_WEB_CELL_HIGH_WARNING_MV=3600
```

Docker Compose passes all six settings through to the application. Defaults
apply when the settings are omitted. Configuration is rejected at startup
unless:

```text
low critical < low warning < high balancing < high warning
0 <= deadband < scale
```

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

- Every supported version 0.1 module has an identity `cell_count` of 15. A
  complete current capture therefore contains exactly the contiguous parser
  indices `0..14`.
- A capture with fewer or more than 15 cells, a missing index or a duplicate
  index is invalid as a whole. It is never presented as a partially current
  module row.
- Only a complete, valid and non-stale 15-cell capture contributes to its
  module average and the shared color scale.
- Retained stale or invalid values may be displayed only for diagnostics and
  must be explicitly marked as stale or invalid.
- A last complete retained capture may fill all 15 tiles when the row is
  explicitly marked stale or invalid, but it does not contribute to the
  average or color scale.
- If a module has never produced a complete valid capture, its row contains
  15 `N/A` cell tiles and no module cell average.
- Invalid, stale and unavailable tiles use a neutral treatment outside the
  blue-white-red measurement scale.
- If no module has a valid current capture, the UI uses neutral tiles and
  displays a clear unavailable-state message.

## Refresh behavior

- Current-state sections refresh through HTMX without a full-page reload.
- The default refresh interval is 5 seconds.
- One timezone-aware UTC `generated_at` snapshot is used for every age and
  staleness calculation in one rendered page or fragment response.
- A refresh failure leaves the last successfully rendered page visible.
- The next successful response clearly communicates the current service,
  acquisition and freshness state.
- Full-page navigation and refresh remain functional without HTMX.

### Transient cell-voltage change indication

The rack heatmap provides a transient browser-local indication when a primary
cell-voltage measurement changes between successful HTMX refreshes:

- only the primary integer-mV cell-voltage text inside a heatmap tile
  participates;
- comparison identity is the stable module barcode plus zero-based parser cell
  index `0..14`; current rack position alone is not an identity;
- when both the previous and new values are numeric and unequal, the new
  primary voltage text uses a readable green foreground for exactly 3 seconds;
- after 3 seconds the text returns to its normal inherited foreground color;
- another numeric change during the indication restarts the 3-second interval
  from the latest change;
- initial page load, full-page reload and the first appearance of a module or
  cell do not trigger the indication;
- equal values and transitions to or from `N/A`, invalid, stale or unavailable
  data do not trigger the indication.

The signed deviation, module average, module voltage, rack measurements,
timestamps, ages, status labels, backgrounds and absolute-state borders do not
participate. The effect does not change the fixed relative scale, deadband,
absolute voltage thresholds or BMS-status precedence.

Comparison state and timers exist only in the current browser page. The
feature introduces no backend history, persistence, REST field or acquisition
change. Without JavaScript, current voltage values remain visible and the
read-only UI remains fully functional.

The green foreground and a transient CSS class identify the changed value.
This effect is informational only and must not represent safety, validity,
freshness or alarm state.

## Ordering and formatting

- Present modules are ordered by current position.
- Stable barcodes are used for module links and identity.
- Cell measurements and human-facing heatmap/detail labels retain their
  parser-provided zero-based indices `0..14`.
- Units remain explicit.
- Unavailable values are not converted to zero.
- Device states and unknown enum values remain visible strings.
- `raw_payload` is never rendered.
- Device-provided values and error details are HTML-escaped.

## Testing

Tests use controlled `CurrentStateStore` snapshots and a fixed clock. They
must verify:

- rack overview rendering and required values;
- all four MQTT badge states and optional MQTT status details;
- every discovered module appears in position order;
- module links and lookup use stable barcodes;
- unknown-module HTTP 404 behavior;
- every modeled cell appears and every available heatmap tile contains its
  numeric voltage;
- average cell-voltage calculation;
- independent per-module reference means;
- module-terminal voltage and derived module cell average columns;
- exact-zero deviation uses the neutral class;
- positive deviation uses the red side and negative deviation the blue side;
- the inclusive neutral deadband, fixed symmetric scale, endpoint saturation
  and all-neutral safe case;
- the relative scale remains unchanged for snapshots with different current
  maximum deviations;
- default visualization settings and environment overrides;
- invalid threshold ordering, negative deadband and non-positive scale fail
  configuration;
- every exact absolute threshold boundary;
- non-normal BMS voltage status takes precedence over numeric thresholds;
- absolute voltage state remains understandable without color and does not
  obscure the relative-deviation background;
- exactly 15 ordered cell columns labeled `Cell 0` through `Cell 14`;
- incomplete captures invalidate the entire module row;
- invalid and stale groups are excluded from the reference mean;
- invalid, stale and unavailable values are visibly marked;
- unavailable values render as `N/A`, never zero;
- stale values are not presented as current;
- status remains understandable without color;
- Jinja2 escaping prevents device values or errors from becoming markup;
- HTMX fragments use the same query/view-model layer as full pages and REST;
- web requests execute no console commands and start no polling;
- no write or arbitrary-command routes are introduced;
- no MQTT configuration or control operation is introduced;
- existing REST behavior and tests remain unchanged;
- initial load, unchanged values and first appearances do not trigger the
  transient cell-voltage change indication;
- changed numeric cell voltage triggers only its primary text for 3 seconds,
  another change restarts the timer, and the class is then removed;
- cell change comparison uses stable barcode plus zero-based cell index across
  rack-position changes;
- `N/A`, invalid, stale and unavailable transitions do not trigger the change
  indication;
- deviation text, backgrounds, absolute-state borders and unrelated values
  remain unaffected by the change indication;
- Playwright browser rendering at desktop `1440x900` and narrow `390x844`
  viewports.

## Verification

```text
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m mypy src tests
python -m pytest tests/browser
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
- Grafana dashboards and alert rules;
- a temperature heatmap as a required deliverable;
- authentication and authorization;
- configuration editing;
- per-cell pages;
- write operations;
- arbitrary console commands;
- independent polling, parsing or discovery;
- changes to the REST response contract.
