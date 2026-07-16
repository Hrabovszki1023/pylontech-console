# ADR-002: Technology stack for version 0.1

## Status

Accepted for version 0.1.

## Context

The project shall provide a read-only service for Pylontech battery racks connected through a Waveshare serial-to-Ethernet gateway.

The service must:

- communicate with the Pylontech console over TCP,
- serialize console commands and parse text responses,
- discover connected modules dynamically,
- identify modules by barcode independently of their current rack position,
- expose current values through MQTT, REST and a read-only web UI,
- persist module inventory and topology changes,
- run reliably as a Docker container,
- remain simple enough to implement and operate on a small Proxmox host.

The protocol contracts and domain model remain implementation-language independent. This ADR defines the reference implementation for version 0.1.

## Decision

Version 0.1 will be implemented as one Python service.

Selected technologies:

| Area | Decision | Purpose |
|---|---|---|
| Language | Python 3.13 | Reference implementation |
| Concurrency | `asyncio` | TCP connection, command queue and polling |
| Web/API | FastAPI | REST API, health endpoints and web server |
| Data models/configuration | Pydantic | Typed domain models and validated configuration |
| MQTT | `paho-mqtt` | Publishing values for ioBroker and other consumers |
| Inventory persistence | SQLite | Known modules, positions and topology events |
| Database access | SQLAlchemy | Explicit and testable persistence layer |
| Web UI | Jinja2 plus HTMX | Simple read-only status pages without a separate frontend build |
| Testing | pytest | Parser, domain, integration and smoke tests |
| Code quality | Ruff and mypy | Linting, formatting checks and static typing |
| Deployment | Docker and Compose | Reproducible operation on Proxmox |

## Architectural form

The application is one deployable service with internally separated components:

```text
pylontech-console-service
├── TCP transport
├── serialized command scheduler
├── protocol parsers
├── discovery and inventory
├── current in-memory state
├── SQLite inventory repository
├── MQTT publisher
├── REST API
└── read-only web UI
```

The service is deliberately not split into multiple microservices in version 0.1. The components require the same state and the same exclusive console connection. Additional processes would add deployment and synchronization complexity without providing a corresponding benefit.

## Reasons for the decisions

### Python

Python is well suited to the dominant tasks in this project: asynchronous TCP communication, parsing structured text, MQTT integration, SQLite access and small web applications. It also allows the captured console responses to be used directly as parser test fixtures.

Python is the language of the reference implementation, not part of the external protocol contract. A future implementation in another language remains possible if it satisfies the same contracts.

### `asyncio`

Only one command may use the Pylontech console connection at a time. An asynchronous command queue provides:

- one active command at a time,
- polling without parallel access to the console,
- explicit timeouts,
- reconnection after network failure,
- prioritization of discovery and normal polling,
- integration with the FastAPI runtime.

Thread-based parallelism is not required for this I/O-bound workload.

### FastAPI and Pydantic

FastAPI provides a typed REST API and health endpoints with little framework overhead. Pydantic provides validation for configuration and external response models. Both reduce implicit assumptions in the implementation.

Django was rejected as unnecessarily large for a read-only service. Flask would work, but would require more manually defined validation and API contracts.

### Jinja2 and HTMX

The user interface is a read-only operational view, not a separate product. Server-side rendering and small partial updates are sufficient for:

- rack overview,
- module details,
- health and communication state,
- cell-voltage and temperature heat maps.

React or Vue would introduce a second build toolchain and duplicate client-side data models without a clear version 0.1 benefit.

### MQTT

MQTT is the primary integration interface for ioBroker and time-series processing. It maps naturally to current rack, module and cell values and allows consumers to subscribe selectively.

Modbus TCP is intentionally outside version 0.1 because the barcode-based and nested cell model is less natural to represent in fixed register ranges.

### SQLite

SQLite is sufficient for persistent inventory data:

- known module barcodes,
- first and last observation,
- current and previous position,
- firmware and hardware identity,
- topology events.

It requires no additional database service. High-frequency measurement history is not stored in SQLite; it is published through MQTT for ioBroker/InfluxDB/Grafana.

### Docker

Docker provides a reproducible runtime, isolated dependencies, health checks and straightforward deployment on Proxmox. The container shall run without privileged permissions and use a persistent `/data` volume.

## Configuration

Configuration shall be validated at startup. Environment variables override an optional YAML configuration file, which overrides documented defaults.

Required configuration areas:

- Waveshare host and TCP port,
- TCP connection and response timeouts,
- MQTT host, port and optional credentials,
- polling intervals,
- HTTP listening address and port,
- SQLite database path,
- log level.

Secrets shall not be stored in the repository.

## Consequences

### Positive

- one simple deployable unit,
- strong support for protocol parsing and automated tests,
- shared typed model for MQTT, REST and UI,
- no separate frontend build,
- no external database required,
- easy deployment on the existing infrastructure.

### Negative

- Python is not the most resource-efficient option,
- synchronous libraries such as `paho-mqtt` require careful integration with the asynchronous application,
- SQLite permits only limited write concurrency, which is acceptable because inventory writes are infrequent,
- HTMX limits the UI to comparatively simple interactions, which is intentional for version 0.1.

## Out of scope for version 0.1

- Modbus TCP server,
- direct InfluxDB integration,
- writable settings page,
- user and role management,
- control or configuration commands sent to the BMS,
- multiple independent Pylontech racks in one process,
- separate frontend application.

## Review trigger

This decision shall be reviewed if one of the following occurs:

- the service must support many racks concurrently,
- SQLite becomes a bottleneck,
- the web UI requires substantial client-side interaction,
- Python runtime or memory consumption becomes operationally relevant,
- a required library proves unreliable in the target environment.
