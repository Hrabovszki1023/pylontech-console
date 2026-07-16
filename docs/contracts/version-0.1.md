# Product Contract — Version 0.1

## Status

Accepted for implementation.

## Objective

Version 0.1 shall provide a read-only microservice that automatically discovers a Pylontech battery rack through the console interface, reads rack, module and cell data, identifies physical modules by barcode, publishes current values through MQTT, exposes the same current state through a read-only web interface and REST API, and operates reliably without manual module configuration.

The implementation shall prioritize observability. It shall not modify battery configuration or operating state.

## Scope

Version 0.1 includes:

- TCP communication with the Waveshare serial-to-Ethernet gateway,
- automatic rack and module discovery,
- barcode-based stable module identity,
- cyclic acquisition of rack, module and cell data,
- MQTT publication,
- a read-only status web interface,
- a read-only REST API,
- local persistence of the module inventory and topology history,
- health, freshness and communication status,
- automatic reconnect and recovery,
- containerized deployment.

## Out of scope

Version 0.1 explicitly excludes:

- battery control commands,
- configuration changes on the Pylontech system,
- arbitrary console-command execution,
- Modbus TCP output,
- direct InfluxDB integration,
- Grafana integration inside the service,
- editable settings through the web interface,
- user management and authentication,
- firmware updates,
- EEPROM, flash, SOC calibration or protection-setting access,
- historical charts in the built-in web interface.

Historical visualization is expected to be implemented externally through the chain:

```text
Microservice -> MQTT -> ioBroker -> InfluxDB -> Grafana
```

## Safety boundary

The service shall only execute explicitly allowlisted read-only commands.

Initial production allowlist:

```text
pwr
pwrsys
info <position>
pwr <position>
bat <position>
```

Additional documented read-only commands may be used only after they are explicitly added to this contract.

The implementation shall not expose a generic production API such as:

```text
execute arbitrary console command
```

Commands that modify state, configuration, protection limits, memory, EEPROM, flash, SOC data, firmware or MOSFET state are prohibited in Version 0.1.

## Module discovery

No module count and no module-address list shall be configured manually.

The service shall determine the currently present module positions from `pwr`.

For every present position, the service shall execute:

```text
info <position>
```

The returned barcode shall be used as the stable physical module identity.

## Identity and topology

The following distinction is mandatory:

```text
Barcode = stable physical identity
Position = current rack address/topology
```

Module data shall be stored under the barcode, not under the current rack position.

The service shall maintain both mappings:

```text
position -> barcode
barcode -> module data and current position
```

A module moved during maintenance shall retain its previous identity and history.

A different barcode found at an existing position shall update the topology mapping and shall not overwrite the data of the previously installed module.

Removed modules shall remain known in the local inventory and shall be marked as not currently present.

Missing, empty or duplicate barcodes shall be treated as inventory errors and shall be visible through health status, logs, MQTT and the web interface.

See also:

```text
docs/architecture/adr-001-module-identity-and-position.md
```

## Internal data model

The implementation shall represent the current system state conceptually as:

```text
PylonSystem
├── connection
├── rack
│   ├── measurements
│   ├── limits
│   ├── status
│   └── positions[position] -> barcode
└── modules[barcode]
    ├── identity
    ├── current_position
    ├── present
    ├── measurements
    ├── states
    ├── cells[]
    └── freshness
```

The module collection shall be dynamic.

Cell indices shall preserve the console's zero-based indexing internally. Presentation layers may additionally show human-readable cell numbers 1 through n.

## Polling and discovery

Discovery and cyclic process-data polling shall be separate concerns.

### Startup discovery

At service startup:

1. establish the TCP connection,
2. execute `pwr`,
3. determine all present positions,
4. execute `info <position>` for every present position,
5. build the position-to-barcode mapping,
6. compare the discovered topology with persisted inventory data,
7. emit topology events where applicable.

### Cyclic acquisition

Recommended default intervals:

```text
Rack and cell process data:     5 seconds
Module detail data:            60 seconds
Inventory rediscovery:        300 seconds
```

The exact intervals shall be configurable.

The service shall trigger immediate rediscovery when `pwr` indicates a topology change.

Only one console command may be outstanding on a connection at a time.

## Required command parsers

Version 0.1 requires production parsers for:

```text
pwr
pwrsys
info <position>
pwr <position>
bat <position>
```

The following commands are documented but are not required for the minimum production polling path:

```text
help
stat
time
ci
soh <position>
getpwr
```

`getpwr` shall not be used for production acquisition in Version 0.1 because not all returned fields are identified with sufficient confidence.

## Transport contract

The transport shall connect to the Waveshare gateway through TCP using configurable host and port values.

The Waveshare IP address and port shall not be hard-coded.

A successful response is framed by:

```text
@
... payload ...
Command completed successfully
$$
```

Transport handling shall:

- ignore command echo before `@`,
- start payload collection at `@`,
- stop payload collection at `$$`,
- treat missing start or end markers as an incomplete response,
- retain raw responses for diagnostics,
- preserve unknown fields where possible,
- reject partial responses as valid current data,
- serialize all console access,
- reconnect automatically after network or gateway failure.

`<INTERRUPT>` is not part of the Pylontech protocol. It was produced by PuTTY when Ctrl+C was used during manual capture. It shall be removed from stored captures and ignored defensively if encountered in terminal input.

## Configuration

Version 0.1 shall support configuration through a file and/or environment variables.

Minimum configuration parameters:

```yaml
waveshare:
  host: 192.168.20.211
  port: 4196
  connect_timeout_seconds: 5
  response_timeout_seconds: 3

polling:
  rack_interval_seconds: 5
  module_interval_seconds: 60
  inventory_interval_seconds: 300

mqtt:
  enabled: true
  host: <mqtt-broker>
  port: 1883
  topic_prefix: pylontech
```

Configuration values shall be validated on startup.

Version 0.1 does not require editing configuration through the web interface.

## MQTT contract

MQTT shall be the primary integration interface for ioBroker and downstream automation.

Primary module topics shall use the barcode as the stable key.

Example topic structure:

```text
pylontech/status/online
pylontech/status/state
pylontech/status/last_success
pylontech/status/error

pylontech/rack/system/voltage
pylontech/rack/system/current
pylontech/rack/system/power
pylontech/rack/system/soc
pylontech/rack/system/soh
pylontech/rack/system/highest_cell_voltage
pylontech/rack/system/lowest_cell_voltage
pylontech/rack/system/cell_delta
pylontech/rack/system/highest_temperature
pylontech/rack/system/lowest_temperature

pylontech/rack/positions/<position>/barcode

pylontech/modules/<barcode>/present
pylontech/modules/<barcode>/position
pylontech/modules/<barcode>/model
pylontech/modules/<barcode>/firmware
pylontech/modules/<barcode>/voltage
pylontech/modules/<barcode>/current
pylontech/modules/<barcode>/soc
pylontech/modules/<barcode>/state
pylontech/modules/<barcode>/cells/<cell-index>/voltage
pylontech/modules/<barcode>/cells/<cell-index>/temperature
pylontech/modules/<barcode>/cells/<cell-index>/balancing
```

Each published data object or topic group shall expose sufficient freshness information to distinguish current from stale values.

Recommended metadata:

```text
received_at
device_time, when available
age_seconds
valid
```

Retained MQTT messages may be used for current state, but stale values shall be clearly marked invalid or offline after communication failure.

## Web interface

Version 0.1 shall include a read-only web interface that uses the same internal data model as MQTT and REST.

The web interface shall not directly query the battery independently.

### Rack view

The rack view shall display at minimum:

- service and connection status,
- time of last successful acquisition,
- detected and present module count,
- rack voltage,
- rack current,
- calculated rack power,
- rack SOC and SOH,
- highest, average and lowest cell voltage,
- cell-voltage delta,
- highest, average and lowest temperature,
- recommended charge and discharge limits,
- current topology: position and barcode.

### Module view

For each module, the interface shall display at minimum:

- barcode,
- current position,
- model,
- firmware information,
- present/not-present state,
- voltage,
- current,
- SOC,
- module state,
- minimum and maximum cell voltage,
- cell-voltage delta,
- cell table with voltage, temperature and balancing state,
- data age and validity.

## REST API

Version 0.1 shall provide a read-only REST API for the same current state shown on the web page and published through MQTT.

Minimum conceptual endpoints:

```text
GET /api/v1/health
GET /api/v1/rack
GET /api/v1/modules
GET /api/v1/modules/{barcode}
GET /api/v1/positions
```

The REST API shall not expose write operations or arbitrary console commands.

## Inventory persistence

The service shall persist module inventory and topology metadata locally, preferably in SQLite.

Persisted information shall include at minimum:

- barcode,
- model,
- firmware and board information,
- first seen timestamp,
- last seen timestamp,
- last known position,
- current present state,
- topology-change events.

High-frequency measurement history does not need to be stored in SQLite.

## Events

The service shall emit and persist topology events when detected:

```text
MODULE_DISCOVERED
MODULE_REMOVED
MODULE_REAPPEARED
MODULE_MOVED
MODULE_REPLACED_AT_POSITION
INVENTORY_ERROR
```

Example:

```json
{
  "event": "MODULE_MOVED",
  "module_id": "HPTCR03170C09377",
  "old_position": 2,
  "new_position": 4,
  "timestamp": "2026-07-17T01:40:48+02:00"
}
```

## Health and failure handling

The service shall expose one of the following operating states:

```text
starting
discovering
online
degraded
offline
```

Health information shall include:

- Waveshare connectivity,
- last successful response time,
- current polling delay,
- consecutive communication failures,
- last communication or parser error,
- inventory consistency,
- MQTT connectivity,
- age and validity of current measurements.

The service shall automatically recover from:

- Waveshare restart,
- TCP disconnect,
- network interruption,
- timeout,
- malformed or incomplete response,
- MQTT broker interruption.

A malformed response shall not overwrite the last known valid value as though it were current.

## Derived values

The service may calculate values that are not directly returned by the console, provided they are clearly identified as derived values.

Required useful derived values include:

- rack power from voltage and current,
- per-module minimum cell voltage,
- per-module maximum cell voltage,
- per-module cell-voltage delta,
- rack-wide cell-voltage delta,
- data age,
- topology-change events.

Derived values shall not be confused with raw BMS values.

## Alarm observations

Version 0.1 may expose observational alarm states, but shall not perform automatic battery control.

Examples:

- communication offline,
- stale data,
- module missing,
- module moved,
- barcode changed at a position,
- duplicate barcode,
- non-normal BMS state,
- excessive cell-voltage delta,
- temperature outside configured observational limits.

Threshold-based alarms shall be configurable and shall not be presented as manufacturer protection limits unless explicitly sourced from the BMS.

## Deployment

Version 0.1 shall be deployable as a Docker container suitable for Proxmox-hosted operation.

The deployment shall provide:

- non-privileged execution,
- persistent configuration and inventory storage,
- container health check,
- automatic restart compatibility,
- structured application logs,
- configurable log level.

## Testing contract

The stored console captures shall serve as parser fixtures.

Automated tests shall cover at minimum:

- parsing all required command responses,
- absent module rows,
- dynamic module count,
- module movement while preserving barcode identity,
- module replacement at a position,
- new module discovery,
- removed and reappearing modules,
- duplicate barcode detection,
- unknown additional fields,
- incomplete response framing,
- timeout and reconnect behavior,
- stale-value handling,
- MQTT topic generation by barcode,
- REST and web data consistency with the internal model.

## Definition of Done

Version 0.1 is complete when all of the following are true:

- no module count or module list needs to be configured,
- all present modules are discovered automatically,
- every module is identified by barcode,
- measurements are stored and published under the barcode identity,
- position-to-barcode resolution is available,
- moving modules does not mix their identities or histories,
- rack, module and cell values are visible in ioBroker through MQTT,
- current values are visible on a read-only web page,
- the same data is available through a read-only REST API,
- inventory and topology changes survive service restarts,
- communication and data freshness are visible,
- the service reconnects automatically after gateway or network failure,
- only allowlisted read-only commands are executed,
- all required parsers are covered by automated fixture-based tests,
- the service runs as a health-checked Docker container.
