# MQTT contract version 0.1

## Status

Accepted for implementation by GitHub issue #33.

This document refines the MQTT requirements in `version-0.1.md`. If the two
documents conflict, implementation must stop until the conflict is resolved
explicitly.

## Purpose and boundaries

MQTT is the primary integration output for ioBroker and downstream
time-series processing. It publishes the authoritative shared
`CurrentStateStore`; it does not own battery state.

```text
CurrentStateStore
        |
shared query/snapshot boundary
        +-- REST
        +-- Web
        `-- MQTT
```

MQTT must use the same values, units, stable identities, validity and
staleness rules as REST and Web. The adapter must not query the Waveshare
gateway, execute console commands, parse protocol responses, start polling or
maintain a duplicate current-state model.

Version 0.1 is publish-only. It subscribes to no application, command or
control topics. Broker messages can never change battery or service state.
Raw console payloads and unsanitized transport details are never published.

## Protocol and delivery

- MQTT protocol: 3.1.1.
- Client library: `paho-mqtt`, as required by ADR-002.
- Session: clean session.
- Character encoding: UTF-8.
- Current-state, metadata, inventory and availability publications use QoS 1
  and retain.
- Topology events use QoS 1 without retain.
- The adapter subscribes to no topics.
- MQTT QoS 1 is at least once. Consumers must tolerate duplicate
  publications and duplicate topology events.
- Publication order across different topics is not transactional. Consumers
  use each group's metadata and `snapshot_at` to determine completeness.

## Configuration

The following environment variables are supported:

| Variable | Default | Validation |
|---|---:|---|
| `PYLONTECH_MQTT_ENABLED` | `false` | Pydantic boolean |
| `PYLONTECH_MQTT_HOST` | none | required and non-empty when enabled |
| `PYLONTECH_MQTT_PORT` | `1883` | integer `1..65535` |
| `PYLONTECH_MQTT_CLIENT_ID` | `pylontech-console` | non-empty UTF-8, no NUL, maximum 128 bytes |
| `PYLONTECH_MQTT_USERNAME` | none | optional non-empty UTF-8 |
| `PYLONTECH_MQTT_PASSWORD` | none | optional; allowed only when username is set |
| `PYLONTECH_MQTT_TOPIC_PREFIX` | `pylontech` | topic-prefix rules below |
| `PYLONTECH_MQTT_KEEPALIVE_SECONDS` | `60` | integer `1..65535` |
| `PYLONTECH_MQTT_CONNECT_TIMEOUT_SECONDS` | `5` | finite number greater than zero |
| `PYLONTECH_MQTT_RECONNECT_MIN_SECONDS` | `1` | finite number greater than zero |
| `PYLONTECH_MQTT_RECONNECT_MAX_SECONDS` | `60` | finite and not less than minimum |
| `PYLONTECH_MQTT_TLS_ENABLED` | `false` | Pydantic boolean |
| `PYLONTECH_MQTT_TLS_CA_FILE` | none | optional readable file when TLS is enabled |
| `PYLONTECH_MQTT_TLS_CERT_FILE` | none | optional; requires key file |
| `PYLONTECH_MQTT_TLS_KEY_FILE` | none | optional; requires certificate file |
| `PYLONTECH_MQTT_TLS_INSECURE` | `false` | boolean; see TLS policy |

MQTT-disabled configuration does not require a host and creates no MQTT
client. Other MQTT values are still validated when supplied.

Passwords must not be logged, published, returned through REST or rendered in
the web UI. Docker Compose passes every listed setting through to the
application. Secrets are supplied by the deployment environment, never stored
in the repository.

### Topic prefix

Leading and trailing whitespace is stripped before validation. No other
normalization is performed.

The prefix:

- is one or more non-empty levels separated by `/`;
- has no leading or trailing `/` and no empty level;
- contains neither MQTT wildcard (`+`, `#`) nor NUL;
- is at most 256 UTF-8 bytes.

Examples:

```text
pylontech
home/energy/pylontech
```

Every topic below is relative to `<prefix>/`.

### TLS policy

When TLS is disabled, CA, certificate, key and insecure settings other than
their defaults are rejected.

When TLS is enabled:

- server certificate verification and hostname verification are enabled by
  default using the operating-system trust store;
- `TLS_CA_FILE` optionally replaces the default CA source;
- client certificate and key are either both present or both absent;
- `TLS_INSECURE=true` explicitly disables hostname verification and must emit
  a warning without exposing credentials.

TLS does not silently change the configured port.

## Topic identity and dynamic segments

Barcode is the stable physical module identity. Position is mutable topology.

```text
modules/<barcode>/...
rack/positions/<position>/barcode
```

A module move changes its `position` value and the position mapping. It does
not change or move its `modules/<barcode>/...` topics.

Barcode is device-provided and therefore encoded as one MQTT topic level:
each UTF-8 byte outside ASCII letters, digits, `-`, `_` and `.` is encoded as
uppercase `%HH`. The literal `%` is encoded as `%25`. Encoding is reversible
and prevents `/`, wildcards, NUL or whitespace from creating topic levels or
collisions. Payload fields retain the original barcode.

Positions and cell indices use canonical unsigned decimal without leading
zeroes. Valid positions are `1..16`; cell indices preserve the parser's
zero-based values.

## Payload rules

Scalar topics contain exactly one UTF-8 value:

- integer: base-10 digits with an optional leading minus;
- finite decimal: JSON number notation, never `NaN` or infinity;
- boolean: lowercase `true` or `false`;
- string or enum: its UTF-8 text without JSON quoting;
- timestamp: ISO 8601 UTC with a `Z` suffix;
- sanitized absent error: an empty payload string.

Units are in topic names. Voltage is mV, current is mA, temperature is
millidegrees Celsius, capacity/coulomb values are mAh, power is W, age is
seconds and SOC/SOH are percent.

No unavailable measurement is fabricated as zero. If a group has never had a
value, its value topics are not published; its metadata says `valid=false`,
`stale=true` and has an empty `received_at`. If an invalid or stale group
retains a last successful value, the value topics remain retained for
diagnostics and the metadata communicates that they are not current.

JSON document topics use compact UTF-8 JSON, sorted object keys and no
non-finite numbers. Unavailable optional fields are JSON `null`. Timestamps
use the same UTC format as scalar topics.

For a retained topic, an empty payload is the MQTT 3.1.1 retained-message
deletion mechanism. The contract deliberately uses it to clear an obsolete
nullable scalar such as an error, timestamp or current position.

The current version 0.1 model has no separately verified `device_time`.
Therefore MQTT publishes service `received_at` timestamps but no
`device_time` topic. A future reliably modeled device time requires an
explicit contract addition and must not be inferred from another timestamp.

## Common group metadata

Every inventory, rack, module-detail and module-cell group publishes:

```text
<group>/meta/snapshot_at
<group>/meta/received_at
<group>/meta/age_seconds
<group>/meta/valid
<group>/meta/stale
<group>/meta/error
```

- `snapshot_at` is the one timezone-aware UTC instant captured for the entire
  publication snapshot.
- `received_at` is empty when no successful value exists.
- `age_seconds` is empty when `received_at` is absent; otherwise it is
  `max(0, snapshot_at - received_at)`.
- `valid` and `stale` are independent.
- `error` is an empty string when absent, otherwise the sanitized current
  error detail.

All topics for one snapshot use the same `snapshot_at` and therefore the same
age/staleness calculation. The adapter publishes group value topics first and
publishes that group's `meta/snapshot_at` last. Consumers may treat a changed
`snapshot_at` as completion of that group's update.

## Service and availability topics

```text
status/online
status/state
status/updated_at
status/last_success_at
status/consecutive_failures
status/error
status/errors
status/snapshot_at
```

- `status/online` is boolean and means that this MQTT client is currently
  connected and has completed its online publication.
- `status/state` is `starting`, `discovering`, `online`, `degraded` or
  `offline` using the combined health rules below.
- nullable timestamps and absent error use an empty payload.
- `status/errors` is a retained compact JSON array with the same sanitized
  error fields and authoritative tuple order as REST.
- `status/error` is the MQTT connection error when MQTT is enabled and
  disconnected; otherwise it is the first `status/errors` detail; otherwise
  it is empty.
- `status/snapshot_at` is published last for the service group.

The retained Last Will is:

```text
topic:   <prefix>/status/online
payload: false
qos:     1
retain:  true
```

After a successful connection the adapter republishes the complete current
snapshot and then publishes `status/online=true` last. A graceful shutdown
publishes retained `status/online=false` and waits for its QoS 1
acknowledgement within the connect timeout before disconnecting. An ungraceful
disconnect causes the broker to publish the retained Last Will.

## Inventory and position topics

Inventory metadata uses:

```text
inventory/meta/...
```

The following retained JSON documents are published:

```text
inventory/modules
rack/positions
```

`inventory/modules` is an array of every currently known barcode sorted
lexicographically. `rack/positions` is an object whose keys are canonical
position strings and whose values are original barcodes, sorted numerically by
position.

For selective subscription, every occupied position also publishes:

```text
rack/positions/<position>/barcode
```

When an observed current position becomes empty or moves to another barcode,
the obsolete per-position retained topic is deleted with a zero-byte retained
QoS 1 publication. The JSON `rack/positions` document is authoritative for a
complete snapshot.

Every known module publishes:

```text
modules/<barcode>/barcode
modules/<barcode>/present
modules/<barcode>/position
modules/<barcode>/first_seen_at
modules/<barcode>/last_seen_at
```

`position` is empty when the module is not currently mapped. Known removed
modules remain under their barcode with `present=false`; their module topics
are not reassigned or deleted merely because they are absent.

“Known” means known to the current process. Version 0.1 intentionally rebuilds
inventory from the battery system after every restart. MQTT does not invent
durable inventory history.

## Rack topics

Rack freshness uses `rack/meta/...`.

All modeled `RackSummary` values except `raw_payload` are retained under:

```text
rack/system/received_at
rack/system/state
rack/system/total_modules
rack/system/present_modules
rack/system/sleeping_modules
rack/system/voltage_mv
rack/system/current_ma
rack/system/remaining_capacity_mah
rack/system/full_charge_capacity_mah
rack/system/soc_percent
rack/system/soh_percent
rack/system/highest_cell_voltage_mv
rack/system/average_cell_voltage_mv
rack/system/lowest_cell_voltage_mv
rack/system/highest_temperature_mc
rack/system/average_temperature_mc
rack/system/lowest_temperature_mc
rack/system/recommended_charge_voltage_mv
rack/system/recommended_discharge_voltage_mv
rack/system/recommended_charge_current_ma
rack/system/recommended_discharge_current_ma
rack/system/system_recommended_charge_voltage_mv
rack/system/system_recommended_discharge_voltage_mv
rack/system/system_recommended_charge_current_ma
rack/system/system_recommended_discharge_current_ma
rack/system/derived/power_w
rack/system/derived/cell_voltage_delta_mv
```

Modeled `extra_fields` are published only as one retained compact JSON object:

```text
rack/system/extra_fields
```

Unknown field names never become topic levels.

## Module identity topics

Every modeled identity value except `raw_payload` is retained below:

```text
modules/<barcode>/identity/manufacturer
modules/<barcode>/identity/device_name
modules/<barcode>/identity/board_version
modules/<barcode>/identity/main_software_version
modules/<barcode>/identity/software_version
modules/<barcode>/identity/boot_version
modules/<barcode>/identity/communication_version
modules/<barcode>/identity/release_date
modules/<barcode>/identity/specification
modules/<barcode>/identity/cell_count
modules/<barcode>/identity/max_discharge_current_ma
modules/<barcode>/identity/max_charge_current_ma
modules/<barcode>/identity/epon_port_rate
modules/<barcode>/identity/console_port_rate
modules/<barcode>/identity/extra_fields
```

`extra_fields` is a compact JSON object and its keys never become topic
levels.

## Module-detail topics

Freshness uses:

```text
modules/<barcode>/detail/meta/...
```

Every modeled `ModuleDetail` field except `raw_payload` is retained below:

```text
modules/<barcode>/detail/received_at
modules/<barcode>/detail/position
modules/<barcode>/detail/voltage_mv
modules/<barcode>/detail/current_ma
modules/<barcode>/detail/temperature_mc
modules/<barcode>/detail/soc_percent
modules/<barcode>/detail/total_coulomb_mah
modules/<barcode>/detail/max_voltage_mv
modules/<barcode>/detail/charge_times
modules/<barcode>/detail/basic_status
modules/<barcode>/detail/discharge_seconds
modules/<barcode>/detail/voltage_status
modules/<barcode>/detail/current_status
modules/<barcode>/detail/temperature_status
modules/<barcode>/detail/coulomb_status
modules/<barcode>/detail/soh_status
modules/<barcode>/detail/heater_status
modules/<barcode>/detail/enabled_protections
modules/<barcode>/detail/battery_events_raw
modules/<barcode>/detail/battery_events
modules/<barcode>/detail/power_events_raw
modules/<barcode>/detail/power_events
modules/<barcode>/detail/system_fault_raw
modules/<barcode>/detail/system_fault
modules/<barcode>/detail/charge_seconds
modules/<barcode>/detail/extra_fields
```

`enabled_protections` is a compact JSON array. `extra_fields` is a compact JSON
object. Nullable duration fields use an empty payload when unavailable.

## Module-cell topics

Cell-group freshness uses:

```text
modules/<barcode>/cells/meta/...
```

The group publishes these retained derived values:

```text
modules/<barcode>/cells/count
modules/<barcode>/cells/derived/minimum_voltage_mv
modules/<barcode>/cells/derived/maximum_voltage_mv
modules/<barcode>/cells/derived/voltage_delta_mv
modules/<barcode>/cells/derived/minimum_temperature_mc
modules/<barcode>/cells/derived/maximum_temperature_mc
```

Every modeled cell publishes:

```text
modules/<barcode>/cells/<cell-index>/voltage_mv
modules/<barcode>/cells/<cell-index>/current_ma
modules/<barcode>/cells/<cell-index>/temperature_mc
modules/<barcode>/cells/<cell-index>/soc_percent
modules/<barcode>/cells/<cell-index>/coulomb_mah
modules/<barcode>/cells/<cell-index>/balancing
modules/<barcode>/cells/<cell-index>/base_status
modules/<barcode>/cells/<cell-index>/voltage_status
modules/<barcode>/cells/<cell-index>/current_status
modules/<barcode>/cells/<cell-index>/temperature_status
```

If a newly valid complete group has fewer indices than a previously retained
group, obsolete per-cell topics are deleted before publishing the new group.
The version 0.1 web contract independently requires 15 contiguous cells for a
current US2000C heatmap row; MQTT nevertheless serializes the authoritative
modeled group and does not fabricate missing cells.

## Topology events

Each newly appended in-process topology event is published once by the
adapter to:

```text
events/topology
```

The non-retained compact JSON payload is:

```json
{
  "barcode": "HPTCR03170C09377",
  "detail": "module moved",
  "kind": "MODULE_MOVED",
  "position": 4,
  "previous_position": 2,
  "replaced_barcode": null,
  "timestamp": "2026-07-17T00:40:48Z"
}
```

Events are published in their authoritative state order. A reconnect
republishes current retained state but does not replay already emitted
in-process events. MQTT QoS 1 can still duplicate an individual delivery.
Persistent replay is outside Version 0.1.

## Publication triggers and snapshots

The publisher observes state changes through an application/current-state
interface. It publishes after startup state becomes available and after every
subsequent authoritative state publication. It may coalesce intermediate
states while disconnected, but after reconnect it must publish the latest
complete snapshot.

The adapter computes MQTT serialization from one immutable `CurrentState` and
one `snapshot_at`. It does not mutate that state. It does not run an
independent periodic battery poll.

For time-dependent age/staleness to remain observable even when battery state
does not change, the orchestration layer triggers a snapshot publication at
least once per configured rack polling interval. This trigger reads current
state only and sends no console command.

Implementations may suppress a retained publication whose topic, payload,
QoS and retain flag equal the last acknowledged publication in the current
connection. Group `snapshot_at`, `age_seconds`, `stale` and changed state must
not be suppressed. On every reconnect, the suppression cache is discarded and
the full snapshot is republished.

## Failure, reconnect and stale behavior

MQTT connection and publication failures:

- never stop or delay battery polling, REST or Web;
- never invalidate or overwrite battery acquisitions;
- update MQTT health and sanitized error state;
- use exponential reconnect delay beginning at the configured minimum and
  capped at the configured maximum;
- reset the delay after a successful connection;
- republish the full latest retained snapshot after reconnect.

An invalid acquisition publishes `valid=false` immediately while retaining
the last successful values and original `received_at` when available.
Staleness follows the inclusive age rule from `version-0.1.md`. A retained
value is never represented as current merely because it remains on the
broker.

A module removal publishes the new inventory, deletes obsolete position
topics, sets the known module's `present=false` and clears its current
`position`. Last measurements remain retained with their original metadata
for diagnostics.

## MQTT health and combined service status

The internal health/query model and `GET /api/v1/health` expose:

```json
{
  "mqtt": {
    "enabled": true,
    "state": "disconnected",
    "connected": false,
    "last_connected_at": null,
    "last_disconnected_at": "2026-07-26T10:00:00Z",
    "consecutive_failures": 3,
    "error": "MQTT broker unavailable"
  }
}
```

Rules:

- `state` is exactly one of `disabled`, `connecting`, `connected` or
  `disconnected`;
- disabled MQTT has `enabled=false`, `state=disabled`, `connected=false`,
  null timestamps, zero failures and null error; it does not affect service
  status;
- enabled MQTT uses `connecting` while an active broker connection attempt is
  in progress, including the initial attempt;
- enabled MQTT uses `connected` and `connected=true` only while the MQTT
  client has an established broker connection;
- enabled MQTT uses `disconnected` after a failed attempt or lost connection
  while it waits for the next retry;
- enabled and connected MQTT does not lower service status;
- enabled MQTT with `connected=false`, whether `connecting` or
  `disconnected`, makes a battery-otherwise-online service `degraded`;
- `offline` remains reserved for unavailable battery communication;
- a battery `starting` or `discovering` state retains that state while MQTT
  independently reports its connection;
- MQTT error details are sanitized and contain no credentials or complete
  broker/network diagnostics.

MQTT health is runtime state, not battery state. Its addition to the shared
health query is the only REST response change authorized by this contract.

## Web status

The read-only rack overview displays MQTT runtime state independently from
battery/service state. It does not provide MQTT configuration or control.

The visible badge text is determined only from MQTT `state`:

| MQTT state | Badge text | Semantic treatment |
|---|---|---|
| `disabled` | `MQTT DISABLED` | neutral |
| `connecting` | `MQTT CONNECTING` | pending/warning |
| `connected` | `MQTT ONLINE` | success |
| `disconnected` | `MQTT OFFLINE` | error |

Text is always visible; color is not the only state carrier. The status area
also displays, when available:

- last connected time;
- last disconnected time;
- consecutive connection failures;
- sanitized current MQTT error.

It must not render broker password, username, TLS key material or complete
low-level network diagnostics. Full-page and HTMX rack fragments use the same
MQTT health query and status semantics. The module detail page need not repeat
the MQTT status in version 0.1.

The web UI has no MQTT enable switch, broker settings, credential fields,
connect/disconnect action or other write operation. MQTT is enabled and
configured only through validated deployment configuration.

## ioBroker interoperability

The default scalar topic tree is intended for ioBroker's MQTT adapter:

- stable and human-readable topic paths;
- numeric and boolean scalar payloads rather than JSON wrappers for
  measurements;
- explicit units in topic names;
- retained current state for discovery after ioBroker restart;
- barcode-based module paths that survive rack reordering;
- JSON only for collections or values that are intrinsically structured.

Consumers must use `meta/valid`, `meta/stale`, `meta/received_at` and
`meta/snapshot_at`; retained measurements alone do not prove freshness.

## Lifecycle

When MQTT is disabled, application startup and shutdown are unchanged.

When enabled:

1. create the MQTT adapter without blocking the asyncio event loop;
2. configure credentials, TLS and Last Will before connecting;
3. start broker connection concurrently with normal service startup;
4. expose connection progress through MQTT health;
5. on connection, publish the complete current snapshot and then online state;
6. continue reconnecting independently after failures;
7. on shutdown, stop accepting snapshots, publish graceful offline state,
   wait within the configured timeout, stop the MQTT network loop and release
   resources.

An unavailable broker at startup must not prevent HTTP serving or battery
discovery.

## Testing

Tests use controlled immutable current-state snapshots, a fixed clock and a
controlled MQTT broker.

They must verify:

- configuration defaults and every validation rule;
- disabled operation creates no client or connection;
- exact topic names, payload bytes, QoS and retain flags;
- barcode encoding, reversibility and collision resistance;
- all rack, module, cell, inventory and position fields;
- stable module topics and changed position mappings after a module move;
- current-value metadata, one-snapshot age and inclusive staleness;
- unavailable, retained-invalid and retained-stale values;
- sanitized errors and absence of raw payloads and credentials;
- Last Will registration, online publication and graceful offline
  publication;
- broker unavailable at startup;
- disconnect, bounded backoff, reconnect and full-snapshot republish;
- no event replay on reconnect and tolerance of QoS 1 duplicates;
- obsolete position and cell retained-topic deletion;
- topology-event payload and non-retained delivery;
- MQTT performs no console access, parsing or polling;
- REST and Web remain operational during broker failure;
- `/api/v1/health` MQTT fields and combined service-state rules;
- rack-overview badge text, details, sanitization and HTMX refresh for every
  MQTT state;
- absence of MQTT configuration or control operations in the web UI;
- Docker Compose passes all MQTT environment settings;
- integration against a real test broker;
- live ioBroker verification on the Proxmox Docker host.

Repository verification:

```text
python -m pytest
python -m ruff check .
python -m mypy src tests
docker build -t pylontech-console .
docker compose config
```

Long-running and broker-recovery tests use controlled
start/request/interruption/recovery/termination checks.

## Out of scope

- MQTT command or control subscriptions;
- Home Assistant MQTT Discovery;
- Sparkplug B;
- multiple racks in one process;
- direct InfluxDB or Grafana integration;
- high-frequency measurement persistence;
- durable inventory or persistent event replay;
- broker installation or administration;
- web-based MQTT configuration;
- changes to battery polling, protocol parsing or the read-only command
  allowlist.
