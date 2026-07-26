# Pylontech Console

Open documentation and reference implementation for the undocumented Pylontech RS232 debug console.

## Goal

Pylontech Console is a **read-only monitoring service** for Pylontech battery systems.

Version 0.1 focuses on:

- automatic discovery of installed modules;
- stable module identification by barcode;
- protocol documentation;
- parser implementation based on recorded captures;
- REST API;
- MQTT;
- read-only Web UI including cell heat maps;
- SQLite inventory.

No write commands are implemented in Version 0.1.

## Design Principles

- Contract first
- Read-only
- Barcode = physical identity
- Position = current rack topology
- Automatic discovery
- One internal data model
- Multiple output interfaces (REST, MQTT, Web)

## Architecture

Pylontech → TCP Transport → Response Framing → Parsers → Domain Model → Discovery/Inventory → REST / MQTT / Web / SQLite

## Repository Structure

- docs/architecture - ADRs
- docs/contracts - Version contracts
- docs/development - Implementation plan
- docs/testing - Test strategy
- protocol/ - Protocol specification
- captures/ - Recorded console responses
- src/ - Python implementation
- tests/ - Unit and integration tests

## Entry Point

Development starts with:

1. implementation-plan-v0.1.md
2. ADRs
3. Version contract
4. Protocol documentation
5. Captures

## Important Documents

- docs/contracts/version-0.1.md
- docs/architecture/
- docs/development/implementation-plan-v0.1.md
- docs/testing/test-strategy-v0.1.md
- CONTRIBUTING.md

## Current Status

- Reverse engineering completed.
- Core protocol documented.
- Architecture defined.
- Implementation ready to start.

## Safety

The console exposes read and write commands. Version 0.1 intentionally implements read-only functionality only.

## MQTT

MQTT is disabled by default. To publish the read-only current state, provide at
least:

```bash
export PYLONTECH_MQTT_ENABLED=true
export PYLONTECH_MQTT_HOST=192.168.1.10
docker compose up --build -d
```

The default port is `1883`, client ID is `pylontech-console`, topic prefix is
`pylontech`, and all current-state publications use QoS 1 with retained
payloads. Optional deployment variables configure username/password, TLS,
keepalive, connection timeout, and reconnect limits. Docker Compose passes the
complete `PYLONTECH_MQTT_*` configuration through to the service; the exact
variables and validation rules are defined in
[`docs/contracts/mqtt-v0.1.md`](docs/contracts/mqtt-v0.1.md).

The rack page and `GET /api/v1/health` show MQTT connection state. MQTT remains
publish-only: it subscribes to no command topics and cannot change battery
state.
