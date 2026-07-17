# Dependency rules

## Status

Accepted for version 0.1.

## Purpose

These rules keep components independently implementable and testable. Dependencies point inward toward protocol-independent behavior; delivery and infrastructure details must not leak into parsers or the domain model.

## Specification priority

When sources disagree, use this order and stop before implementing a contradiction:

1. accepted product contracts under `docs/contracts/`,
2. accepted architecture documents and ADRs under `docs/architecture/`,
3. the GitHub issue for the bounded change,
4. existing source code.

An issue may narrow work but may not override a contract or accepted architecture silently.

## Allowed dependencies

```text
transport       -> standard/library abstractions only
framing         -> raw transport data types
parsers         -> framed payload types + domain value types
domain          -> no infrastructure or output layer
discovery       -> domain + console-client abstraction + repository abstraction
persistence     -> domain persistence records/interfaces
outputs/api     -> application/current-state query interfaces
outputs/web     -> application/current-state query interfaces
outputs/mqtt    -> application/current-state query/event interfaces
orchestration   -> composes all layers through explicit interfaces
```

Configuration and application startup may construct concrete adapters, but shall not move their behavior into the domain layer.

## Forbidden dependencies

- Domain must not import FastAPI, MQTT, SQLAlchemy, Jinja2/HTMX or TCP transport code.
- Parsers must not import transport, discovery, persistence, REST, web or MQTT implementations.
- Framing must not know command-specific fields or domain meaning.
- Transport must not parse command payloads or update domain state.
- Discovery must not parse raw console text.
- Persistence must not execute console commands or publish MQTT/HTTP output.
- REST, web and MQTT must not access the Waveshare gateway directly.
- REST, web and MQTT must not implement separate polling, parsing or duplicate current-state models.
- No production component may expose arbitrary console-command execution.
- No layer may bypass the version 0.1 read-only command allowlist.

## Stable abstractions

The following boundaries shall be expressed through explicit interfaces, protocols or narrow callable contracts when implemented:

- console command execution,
- current-state queries and updates,
- inventory repository,
- topology event sink,
- MQTT publisher,
- time source where freshness logic requires deterministic tests.

Concrete implementations are wired at the application composition boundary.

## Data ownership

- Transport owns connection state and raw exchange diagnostics.
- Framing owns response completeness.
- Parsers own conversion from documented payloads.
- Domain/current state owns the authoritative runtime representation.
- Discovery owns position-to-barcode reconciliation.
- Persistence owns durable inventory records.
- Output adapters own serialization for their channel, not the underlying state.

## Read-only enforcement

Read-only safety is defense in depth:

1. the product contract defines the allowlist,
2. command construction accepts only typed, allowlisted operations,
3. the scheduler rejects commands outside the allowlist,
4. no generic arbitrary-command production API is provided,
5. tests verify that only approved commands are emitted.

## Change rule

A new dependency direction, shared model, top-level package or output channel requires an explicit architecture update. Implementation convenience alone is not sufficient justification to violate these rules.
