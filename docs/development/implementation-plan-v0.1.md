# Implementation plan for version 0.1

## Status

Initial implementation sequence. The order may be adjusted when implementation findings require it, but scope changes must remain consistent with the version 0.1 contract.

## Principle

Each step shall produce a usable and testable result. Later layers shall use the same internal domain model instead of implementing separate access paths.

## Step 1: Project skeleton

Create the Python package and development infrastructure:

- `pyproject.toml`,
- source package layout,
- pytest configuration,
- Ruff and mypy configuration,
- basic application entry point,
- initial Dockerfile and Compose file,
- configuration model with safe defaults.

Result: the empty service starts locally and in Docker and exposes a health endpoint.

## Step 2: TCP transport and response framing

Implement communication with the Waveshare gateway:

- TCP connect and disconnect,
- one serialized command queue,
- command terminator,
- response collection from `@` through `$$`,
- removal or ignoring of terminal echo, prompts and terminal artifacts such as `<INTERRUPT>`,
- command timeout,
- reconnect with backoff,
- raw-response retention for diagnostics,
- strict read-only command allowlist.

Result: the service can execute a permitted command and return one complete framed response.

## Step 3: Capture-based protocol parsers

Implement and test parsers in this order:

1. `info <position>`,
2. `pwr`,
3. `pwr <position>`,
4. `bat <position>`,
5. `pwrsys`.

All existing captures shall be used as test fixtures. Unknown fields shall be preserved where applicable, and missing values shall not be converted to zero.

Result: captured responses are converted into typed domain objects.

## Step 4: Domain model and current state

Create the internal model for:

- rack state,
- rack positions,
- modules indexed by barcode,
- module identity and current position,
- cells,
- measurements and states,
- timestamps, validity and data age,
- service health and communication state.

The model shall implement ADR-001:

```text
position -> barcode -> module data
```

Result: all later outputs consume one consistent in-memory state.

## Step 5: Dynamic discovery

Implement self-configuration of the rack:

1. execute `pwr`,
2. determine present positions,
3. execute `info <position>` for every present position,
4. read the barcode,
5. update the position-to-barcode mapping,
6. detect added, removed, moved or replaced modules,
7. reject missing or duplicate barcodes as inventory errors.

No module count or module list shall be configured manually.

Result: the service builds a complete inventory automatically.

## Step 6: Cyclic polling

Implement polling through the same serialized command scheduler:

- rack summary through `pwrsys`,
- module details through `pwr <position>`,
- cell data through `bat <position>`,
- periodic topology verification through `pwr`,
- rediscovery after a detected topology change,
- partial failure handling so that one failed module does not invalidate all other current data.

Polling intervals shall be configurable. Initial defaults are provisional and must be validated against real response times.

Result: current rack, module and cell values are continuously available.

## Step 7: Read-only REST API

Expose the current internal state:

- service health,
- rack overview,
- current position mapping,
- module list,
- module details by barcode,
- module lookup through position,
- current cell values,
- recent topology events.

Result: the service can be inspected and tested without the web UI or MQTT.

## Step 8: Read-only web UI and heat maps

Implement server-rendered pages using Jinja2 and HTMX:

- rack status,
- connection and data-age status,
- module overview,
- module detail pages,
- voltage heat map across all modules and cells,
- optional temperature heat map,
- numeric value shown in every heat-map cell,
- module and rack voltage spread,
- clear indication of stale or invalid data.

Heat-map colors shall show relative deviation while keeping the numeric values visible. Color alone shall not convey status.

Result: outliers are directly visible without requiring ioBroker or Grafana.

## Step 9: MQTT publishing

Publish the same internal state to MQTT:

- retained availability and inventory topics,
- rack values,
- position-to-barcode mapping,
- module values under the stable barcode ID,
- cell values,
- timestamps and validity,
- topology events,
- connection and error status.

No MQTT-specific duplicate polling or parser logic is permitted.

Result: ioBroker can consume all relevant values.

## Step 10: SQLite inventory persistence

Persist only long-lived inventory information:

- known barcode IDs,
- first and last seen timestamps,
- model and firmware identity,
- current and previous positions,
- topology events.

Do not store high-frequency measurement history in SQLite.

Result: module identity and maintenance-related moves survive service restarts.

## Step 11: Operational hardening

Complete the version for continuous operation:

- structured logging,
- Docker health check,
- graceful shutdown,
- reconnect and retry behavior,
- bounded raw-response diagnostics,
- configuration documentation,
- persistent `/data` volume,
- non-privileged container user,
- startup validation,
- clean handling of MQTT unavailability.

Result: the service can run unattended on Proxmox.

## Step 12: Version 0.1 acceptance

Verify the Definition of Done from `docs/contracts/version-0.1.md` against the real rack and Waveshare gateway.

Required acceptance flow:

1. start from an empty persistent data directory,
2. discover the rack without a configured module count,
3. identify every module by barcode,
4. display rack and cell values in the web UI,
5. show the cell voltage heat map,
6. publish data through MQTT,
7. restart the container and retain module inventory,
8. interrupt the Waveshare connection and verify automatic recovery,
9. verify that only allowlisted read-only commands were sent.

## Explicitly deferred

The following shall not delay version 0.1:

- Phase-3 diagnostic console commands,
- Modbus TCP,
- direct InfluxDB support,
- writable configuration UI,
- BMS control functions,
- general OKW reference-project work beyond tests directly useful for this product.
