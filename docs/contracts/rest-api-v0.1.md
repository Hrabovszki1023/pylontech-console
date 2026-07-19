# REST API contract version 0.1

## Status

Accepted for implementation by GitHub issue #19.

This document refines the REST requirements in `version-0.1.md`. If the two
documents conflict, implementation must stop until the conflict is resolved
explicitly.

## Purpose and boundaries

The read-only REST API exposes the authoritative shared `CurrentStateStore`.
It is also the contract for the query/view-model layer shared by the REST API
and the server-rendered web UI.

```text
CurrentStateStore
        |
shared query/view models
        +-- REST API -> JSON
        `-- Web UI -> Jinja2/HTMX -> HTML
```

REST and web must use identical value, unit, ordering, derived-value,
validity, age and staleness rules. Neither adapter may query the Waveshare
gateway, execute console commands, start polling, parse protocol responses or
maintain a duplicate current-state model.

The API must not provide write operations or arbitrary console commands.
`raw_payload` values must never be exposed.

## Endpoints

```text
GET /api/v1/health
GET /api/v1/rack
GET /api/v1/modules
GET /api/v1/modules/{barcode}
GET /api/v1/positions
GET /api/v1/positions/{position}
GET /api/v1/topology-events
```

No per-cell endpoint is required in version 0.1. All current cells are returned
with the module detail.

## Common serialization rules

- Capture one timezone-aware UTC `generated_at` for each response.
- Calculate every age and stale flag in that response against the same
  `generated_at`.
- `age_seconds = max(0, generated_at - received_at)`.
- A value is stale at the inclusive boundary:
  `age >= interval_seconds * stale_after_multiplier`.
- Serialize timestamps as ISO 8601 UTC.
- Keep units explicit in field names, for example `voltage_mv`, `current_ma`
  and `temperature_mc`.
- Serialize unavailable values as JSON `null`, never as a fabricated zero.
- Preserve device states and unknown enum values as strings.
- Serialize immutable mappings and tuples as ordinary JSON objects and arrays.
- Preserve modeled `extra_fields` as JSON objects.
- Omit all `raw_payload` fields.
- Derived values must be nested under `derived`.
- Do not add a redundant global `{ "data": ... }` envelope.

## Current-value envelope

Rack, inventory, module-detail and cell-group values use:

```json
{
  "received_at": "2026-07-19T14:30:00Z",
  "age_seconds": 1.42,
  "valid": true,
  "stale": false,
  "error": null,
  "value": {}
}
```

An invalid acquisition may retain the last successful `value` and
`received_at`; it must set `valid` to `false` and include the sanitized current
error. A value can independently be invalid and not stale, or valid and stale.

An acquisition error contains:

```json
{
  "group": "module",
  "detail": "module acquisition failed",
  "timestamp": "2026-07-19T14:29:55Z",
  "barcode": "HPTCR03170C09377",
  "position": 2
}
```

The optional `barcode` and `position` fields are `null` when unavailable.
Error detail must not contain complete device responses or sensitive transport
details.

## Health

`GET /api/v1/health` returns HTTP 200 while the HTTP application itself is
operating. Its `status` describes acquisition/service health:

```text
starting
discovering
online
degraded
offline
```

- `starting`: process and application initialization is in progress.
- `discovering`: initial inventory discovery is in progress.
- `online`: the most recent required acquisition cycle completed without
  errors.
- `degraded`: usable data exists but a current acquisition or inventory error
  is present.
- `offline`: communication is unavailable and no current acquisition succeeds.

The current-state domain model must add `discovering` so the implementation
matches the product contract.

The health response contains:

- `generated_at`;
- `status`;
- `updated_at`;
- `last_success_at`;
- `consecutive_failures`;
- inventory and rack metadata (`received_at`, `age_seconds`, `valid`, `stale`,
  `error`);
- module-detail counts: `total`, `valid`, `invalid`, `stale`;
- cell-group counts: `module_groups`, `total_cells`, `valid_groups`,
  `invalid_groups`, `stale_groups`;
- sanitized current `errors`.

## Rack

`GET /api/v1/rack` uses the current-value envelope. Its `value` contains every
modeled `RackSummary` field except `raw_payload`, including `extra_fields`.

It also contains:

```json
{
  "derived": {
    "power_w": 59.98,
    "cell_voltage_delta_mv": 6
  }
}
```

Rack power is derived from voltage and current. The rack-wide cell-voltage
delta is highest minus lowest cell voltage. With no acquired rack value, return
HTTP 200 with `value: null`, `valid: false` and `stale: true`.

## Positions

`GET /api/v1/positions` uses the inventory current-value envelope. `value` is
an array sorted by ascending position:

```json
[
  {
    "position": 1,
    "barcode": "HPTCR03170C09377"
  }
]
```

Only currently occupied positions are included. A successfully observed empty
rack is `value: []` with `valid: true`. Inventory that has never been observed
is `value: null` with `valid: false`.

`GET /api/v1/positions/{position}` returns the position, barcode and compact
module summary for an occupied position.

## Module collection

`GET /api/v1/modules` returns:

```json
{
  "generated_at": "2026-07-19T14:30:01Z",
  "modules": []
}
```

Present modules are sorted by current position. Non-present modules follow,
sorted by barcode.

Each compact module summary contains:

- `barcode`;
- nullable `position`;
- nullable `present`;
- `first_seen_at`;
- `last_seen_at`;
- all modeled `ModuleIdentity` fields except `raw_payload`;
- `release_date_raw` exposed without reinterpretation as string field
  `release_date`;
- compact module-detail metadata and the available `voltage_mv`, `current_ma`,
  `temperature_mc`, `soc_percent` and `basic_status`;
- compact cell-group metadata and the available cell `count`;
- derived minimum and maximum cell voltage, cell-voltage delta, and minimum and
  maximum cell temperature.

The collection does not include every cell measurement.

## Module detail

`GET /api/v1/modules/{barcode}` contains:

- stable `barcode`;
- nullable current `position`;
- nullable `present`;
- complete identity as defined for the module collection;
- complete module-detail current-value envelope;
- complete cell-group current-value envelope.

Module detail contains every modeled `ModuleDetail` field except `raw_payload`.
The cell-group `value` is an array containing every modeled cell:

- zero-based `index`;
- `voltage_mv`;
- `current_ma`;
- `temperature_mc`;
- `soc_percent`;
- `coulomb_mah`;
- `balancing`;
- `base_status`;
- `voltage_status`;
- `current_status`;
- `temperature_status`.

## Topology events

`GET /api/v1/topology-events` exposes recent events from the shared current
state, newest first.

Query parameter:

```text
limit: integer, default 100, allowed range 1..1000
```

Each event contains `kind`, `timestamp`, sanitized `detail`, and nullable
`barcode`, `position`, `previous_position` and `replaced_barcode`.

Persistent event history is outside issue #19 and requires the separate
inventory-persistence work.

## HTTP status behavior

- Unknown barcode: HTTP 404.
- Unoccupied but syntactically valid position: HTTP 404.
- Position outside `1..16`: HTTP 422.
- Invalid query parameter, including an out-of-range topology-event limit:
  HTTP 422.
- Known module with unavailable, invalid or stale measurements: HTTP 200 with
  the corresponding metadata and retained/null value.
- Rack or inventory not yet acquired: HTTP 200 with an invalid/stale envelope.

## Technology and application lifecycle

Version 0.1 uses:

- FastAPI for HTTP routing and response validation;
- Pydantic response models;
- Uvicorn as the production ASGI server;
- an application factory accepting state-store/query and clock dependencies
  for deterministic tests.

Issue #19 changes `main.py` from the original skeleton no-op into the
long-running version 0.1 service. The application lifecycle must:

1. create the TCP transport and console client;
2. connect to Waveshare;
3. mark the service as discovering and initialize inventory;
4. start cyclic polling;
5. serve REST through FastAPI/Uvicorn;
6. gracefully stop polling tasks;
7. disconnect TCP during shutdown.

Startup failures must remain visible through health state and logs and must not
create a second polling path.

## HTTP configuration

```text
PYLONTECH_HTTP_HOST=0.0.0.0
PYLONTECH_HTTP_PORT=8000
```

The host must be a valid non-empty bind address. The port must be an integer in
`1..65535`. Docker Compose publishes `8000:8000` by default.

## Testing

Tests use controlled current-state objects and a fixed clock. They must verify:

- every endpoint and response model;
- shared-snapshot age and inclusive stale-boundary behavior;
- health states and aggregate counts;
- rack overview and derived values;
- position mapping and lookup;
- module lookup by barcode;
- complete cell serialization;
- null, invalid and retained-value behavior;
- sanitized errors;
- topology-event ordering and limits;
- 404 and 422 behavior;
- immutable mapping and tuple serialization;
- absence of write and arbitrary-command routes;
- API and web query/view models do not execute console commands or polling;
- application startup and graceful shutdown;
- Docker bind address and port configuration.

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

The long-running local and Docker commands are verified with controlled
start/health-request/termination checks rather than waiting for natural exit.
On the Proxmox Docker host, verify at minimum:

```text
GET /api/v1/health
GET /api/v1/rack
GET /api/v1/positions
GET /api/v1/modules
```

## Out of scope

- web pages, Jinja2 templates, HTMX fragments and heat maps;
- MQTT publication;
- SQLite persistence;
- authentication and authorization;
- configuration editing;
- historical measurements;
- per-cell endpoints;
- write endpoints;
- arbitrary console commands.
