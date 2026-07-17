# Authoritative project structure

## Status

Accepted and authoritative for the initial Python project skeleton.

## Purpose

This document defines the repository layout for the Python reference implementation. GitHub issues and implementation work shall reference this document instead of duplicating the directory tree.

If another document or issue conflicts with this layout, implementation shall stop until the conflict is resolved explicitly.

## Existing documentation

The existing documentation and capture directories remain in place:

```text
docs/
protocol/
captures/
```

Issue #1 must not replace, move, or rewrite their existing contents.

## Target repository layout

```text
pylontech-console/
├── README.md
├── CONTRIBUTING.md
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── docs/
├── protocol/
├── captures/
├── src/
│   └── pylontech_console/
│       ├── __init__.py
│       ├── main.py
│       ├── transport/
│       │   └── __init__.py
│       ├── framing/
│       │   └── __init__.py
│       ├── parsers/
│       │   └── __init__.py
│       ├── domain/
│       │   └── __init__.py
│       ├── discovery/
│       │   └── __init__.py
│       ├── persistence/
│       │   └── __init__.py
│       └── outputs/
│           ├── __init__.py
│           ├── api/
│           │   └── __init__.py
│           ├── mqtt/
│           │   └── __init__.py
│           └── web/
│               └── __init__.py
└── tests/
    ├── unit/
    │   ├── transport/
    │   ├── framing/
    │   ├── parsers/
    │   ├── domain/
    │   └── discovery/
    ├── integration/
    └── fixtures/
```

Python package directories and test directories may contain placeholder files where Git requires them to preserve an otherwise empty directory. Issue #1 shall not add functional implementations to those placeholders.

## Directory responsibilities

| Path | Responsibility |
|---|---|
| `src/pylontech_console/transport/` | TCP connection lifecycle and byte transport |
| `src/pylontech_console/framing/` | Extraction and validation of `@ ... $$` responses |
| `src/pylontech_console/parsers/` | Conversion of framed command payloads into typed domain data |
| `src/pylontech_console/domain/` | Protocol-independent domain types and current-state model |
| `src/pylontech_console/discovery/` | Dynamic rack discovery and position-to-barcode mapping |
| `src/pylontech_console/persistence/` | Inventory and topology persistence abstractions and implementations |
| `src/pylontech_console/outputs/api/` | Read-only REST delivery |
| `src/pylontech_console/outputs/mqtt/` | MQTT publication |
| `src/pylontech_console/outputs/web/` | Read-only server-rendered web UI |
| `tests/unit/` | Isolated tests for individual components |
| `tests/integration/` | Tests across component boundaries |
| `tests/fixtures/` | Test fixture support; canonical console captures remain under `captures/` |
| `docs/` | Product contracts, architecture, development and operational documentation |
| `protocol/` | Command and protocol specifications |
| `captures/` | Sanitized observed console responses used as evidence and parser fixtures |

## Issue #1 boundary

Issue #1 creates only the skeleton and development/build metadata described here.

Issue #1 does not implement:

- configuration models,
- health endpoints,
- TCP transport,
- response framing,
- protocol parsers,
- domain behavior,
- discovery,
- persistence,
- REST endpoints,
- MQTT publication,
- web UI,
- polling or other business logic.

A minimal application entry point may exist only to verify packaging and process startup. It shall not expose functional service behavior.

## Change control

Changes to this layout require an explicit architecture change. An implementation issue may not silently introduce new top-level components or move responsibilities between layers.
