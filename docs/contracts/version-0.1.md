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

`pwrsys` is available only in the authenticated `pylon_debug>` console mode
on the observed firmware. The session lifecycle may additionally issue only:

```text
login <configured-password>
logout
```

These two commands are narrowly authorized for entering and leaving the
required read-only polling mode. They are not polling commands and do not
authorize any other debug/admin command.

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
2. determine the console mode and establish an authenticated debug session as
   defined by the transport contract,
3. execute `pwr`,
4. determine all present positions,
5. execute `info <position>` for every present position,
6. build the position-to-barcode mapping,
7. compare the discovered topology with persisted inventory data,
8. emit topology events where applicable.

Discovery and cyclic polling must not begin until the console session has been
verified as authenticated.

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

The console transport uses these constants:

| Constant | Value |
|---|---:|
| Text encoding | strict ASCII |
| Command terminator | carriage return (`\r`, byte `0x0D`) |
| Response start marker | `@` |
| Response end marker | `$$` |
| Maximum response size | 16 KiB (16,384 bytes) |
| Default connection timeout | 5 seconds |
| Default response timeout | 5 seconds |

A successful response is framed by:

```text
@
... payload ...
Command completed successfully
$$
```

The response prompt follows the framed response and is part of the command
exchange, but not part of the payload:

```text
pylon>
pylon_debug>
```

The transport shall expose the prompt separately and classify the session mode
as `user`, `debug` or `unknown`. Exact prompt matching is required.

Transport handling shall:

- ignore command echo before `@`,
- collect the prompt after `$$` separately from the framed payload,
- start payload collection after `@`,
- stop payload collection before `$$`,
- omit the markers and their adjacent line endings from the returned payload,
- treat missing start or end markers as an incomplete response,
- reject non-ASCII response bytes,
- apply the response timeout to the complete command exchange,
- reject an exchange that exceeds 16,384 bytes before a complete response is found,
- retain raw responses for diagnostics,
- preserve unknown fields where possible,
- reject partial responses as valid current data,
- serialize all console access,
- reconnect automatically after network or gateway failure.

A syntactically complete framed response that rejects a command, including
`Unknown command`, is a command/session failure. It is not by itself evidence
of network or transport corruption and shall not cause a reconnect loop.

### Authenticated console session

The service requires an authenticated debug session because `pwrsys` is a
mandatory Version 0.1 polling command.

After each initial connection and reconnect, the service shall determine the
current mode before sending `login`:

1. issue the already allowlisted `pwrsys` as a one-time capability probe;
2. a successful response followed by exact prompt `pylon_debug>` proves that
   the session is already authenticated;
3. the exact user-mode rejection
   `Unknown command 'pwrsys' - try 'help'` followed by exact prompt `pylon>`
   proves user mode, after which the service sends
   `login <configured-password>`;
4. any other response or prompt leaves the mode `unknown` and fails closed.

Successful authentication requires both
`Command completed successfully` in the framed response and the exact
`pylon_debug>` prompt. Polling remains stopped until both are observed.

`login` is not idempotent. The observed response when it is sent while already
in debug mode contains `Quit current mode`, reports failure and still ends at
`pylon_debug>`. The service shall therefore never use repeated login as a mode
probe.

Every TCP reconnect creates a new unverified application session. The service
shall repeat mode determination and authentication before resuming polling,
even if the gateway or serial device may have retained a previous console
mode.

On controlled shutdown, the service shall best-effort send `logout` only when
the last verified prompt is `pylon_debug>`. A successful logout requires
`Command completed successfully` and exact prompt `pylon>`. Logout failure
shall be sanitized and logged but shall not block process termination.

The login password shall never appear in logs, errors, captures, REST, web,
MQTT or health output. Raw diagnostic retention must redact the full login
command before storage or logging.

`<INTERRUPT>` is not part of the Pylontech protocol. It was produced by PuTTY when Ctrl+C was used during manual capture. It shall be removed from stored captures and ignored defensively if encountered in terminal input.

## Configuration

Version 0.1 shall support configuration through a file and/or environment variables.

Minimum configuration parameters:

```yaml
waveshare:
  host: 192.168.20.211
  port: 4196
  connect_timeout_seconds: 5
  response_timeout_seconds: 5
  login_password_file: /run/secrets/pylontech_console_password

polling:
  rack_interval_seconds: 5
  module_interval_seconds: 60
  inventory_interval_seconds: 300
  stale_after_multiplier: 2

mqtt:
  enabled: true
  host: <mqtt-broker>
  port: 1883
  topic_prefix: pylontech
```

Configuration values shall be validated on startup.

The console login password is mandatory. It shall be supplied by exactly one
of:

```text
PYLONTECH_CONSOLE_LOGIN_PASSWORD
PYLONTECH_CONSOLE_LOGIN_PASSWORD_FILE
```

The file setting is preferred for Docker deployment. Environment variables
remain visible through container inspection and are not a secret store. The
two settings are mutually exclusive. The configured value must be non-empty
strict ASCII and must not contain carriage return, line feed or NUL. One final
line ending read from a password file is removed. Missing, unreadable, empty or
invalid credentials fail startup without echoing the value.

`stale_after_multiplier` shall be configurable, finite and greater than or
equal to `1`. Its default value is `2`. Each data group becomes stale when:

```text
data age >= corresponding polling interval * stale_after_multiplier
```

The corresponding interval is the rack interval for rack and cell data, the
module interval for indexed module data, and the inventory interval for
topology data.

Validity and staleness are separate properties. A failed acquisition marks the
affected data group invalid immediately. Its last successfully received value
and original receive timestamp may remain available for diagnostics. Staleness
depends only on the age rule above, so invalid data may be not stale until its
age reaches the configured threshold.

Version 0.1 does not require editing configuration through the web interface.

## MQTT contract

MQTT shall be the primary integration interface for ioBroker and downstream automation.

The concrete protocol, topic, payload, lifecycle, configuration, health,
failure and verification contract is defined in `mqtt-v0.1.md`.

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

Required metadata is defined by `mqtt-v0.1.md` and includes:

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

The concrete page, heatmap, color, accessibility, refresh, error and
verification contract is defined in `web-ui-v0.1.md`.

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

The concrete endpoint, serialization, error, lifecycle, configuration and
verification contract is defined in `rest-api-v0.1.md`.

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
- non-secret console session mode and authenticated state,
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

Console session health shall expose only:

```text
mode: user | debug | unknown
authenticated: true | false
last_authenticated_at
sanitized_error
```

It shall never expose the configured password or the raw login command.

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

The Waveshare raw TCP console is unencrypted and shall be deployed on a
dedicated isolated technical network or VLAN. Firewall policy shall permit
TCP port 4196 only from the Docker host running this service. Console
authentication is a firmware mode transition, not a network security
boundary. A direct USB/serial transport for a locally attached Raspberry Pi or
Docker host is deferred to a separate future issue.

## Testing contract

The stored console captures shall serve as parser fixtures.

Sanitized fixtures shall cover user-mode `pwrsys` rejection, successful login,
successful debug-mode `pwrsys`, repeated login while already in debug mode and
successful logout. Login fixtures use a placeholder such as `<redacted>` and
must never contain the configured credential.

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
- prompt parsing and `user`, `debug` and `unknown` mode classification,
- already-authenticated startup without repeated login,
- user-mode capability rejection followed by successful authentication,
- failed authentication and unexpected prompt fail closed,
- authentication repeated after every reconnect before polling resumes,
- best-effort logout with verified `pylon>` prompt,
- credential redaction from logs, captures and all output adapters,
- valid command rejection without a transport reconnect loop,
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
