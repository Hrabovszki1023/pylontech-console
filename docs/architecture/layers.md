# Application layers

## Status

Accepted for version 0.1.

## Purpose

The service is one deployable Python application with independently testable internal layers. Each layer has one primary responsibility and communicates through explicit data or interfaces.

## Processing flow

```text
Pylontech console
        |
        v
TCP transport
        |
        v
Response framing
        |
        v
Command parsers
        |
        v
Domain model and current state
        |
        +--> Discovery and inventory
        |
        +--> Persistence
        |
        +--> REST API
        +--> Web UI
        +--> MQTT
```

Console access is serialized. Only one command may be outstanding on the connection at a time.

## Layer responsibilities

### Transport

The transport layer owns:

- TCP connection lifecycle,
- sending bytes for an approved command,
- receiving raw bytes,
- timeouts,
- reconnect behavior,
- bounded raw-response diagnostics.

It does not interpret command payload fields.

### Framing

The framing layer owns:

- ignoring command echo and prompt text outside a response,
- recognizing `@` as response start,
- recognizing `$$` as response end,
- rejecting incomplete responses,
- removing or defensively ignoring terminal artifacts such as `<INTERRUPT>`,
- returning a complete framed payload and framing status.

It does not parse command-specific tables or fields.

### Parsers

Each parser owns one documented command response shape. Parsers:

- consume complete framed payloads,
- preserve unknown data where the command contract requires it,
- represent missing values as missing rather than zero,
- return typed domain data,
- never open network connections or publish output.

Version 0.1 production parsers are defined by the product contract.

### Domain model and current state

The domain layer represents:

- rack state,
- modules keyed by stable barcode,
- current rack position as topology,
- cells and measurements,
- validity, freshness and timestamps,
- health and communication state,
- derived values explicitly distinguished from raw values.

It is independent of TCP, HTML, MQTT and database implementation details.

### Discovery and inventory

Discovery:

- obtains present positions from parsed `pwr` data,
- resolves each present position through `info <position>`,
- builds and updates `position -> barcode`,
- applies ADR-001,
- detects discovered, removed, reappeared, moved or replaced modules,
- reports missing or duplicate barcodes as inventory errors.

Discovery uses abstractions for console commands, state and persistence; it does not parse raw text itself.

### Persistence

Persistence stores long-lived inventory and topology information. It does not store high-frequency measurement history in version 0.1.

The persistence layer must not know the console protocol or presentation formats.

### Outputs

REST, web and MQTT are delivery adapters over the same current domain state.

They:

- do not query the battery independently,
- do not parse console responses,
- do not maintain a competing domain model,
- do not execute console commands,
- remain read-only in version 0.1.

## Cross-cutting orchestration

Application orchestration coordinates:

- the serialized command queue,
- startup discovery,
- cyclic polling,
- state updates,
- persistence of inventory changes,
- publication and presentation,
- graceful startup and shutdown.

Orchestration composes layers but shall not duplicate their implementation responsibilities.

## Testing seams

- Transport is tested with controlled TCP peers.
- Framing is tested with byte/text streams and partial responses.
- Parsers are tested with canonical captures.
- Domain logic is tested without TCP or output adapters.
- Discovery is tested with fake command results and repositories.
- REST, web and MQTT are tested against controlled current-state objects.
- End-to-end integration tests verify composition without weakening layer boundaries.
