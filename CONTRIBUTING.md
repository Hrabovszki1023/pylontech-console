# Contributing

## General Rules
- Do not guess.
- Follow the documented contracts.
- Respect all ADRs.
- Do not invent protocol behaviour.

## Version 0.1
- Strictly read-only.
- Never implement write/configuration commands.
- Parser-first development.
- Tests are mandatory.

## Development Order
1. Transport
2. Framing
3. Parser
4. Domain model
5. Discovery
6. REST
7. Web UI
8. MQTT
9. SQLite

## Definition of Done
- Contracts satisfied.
- Tests passing.
- Documentation updated.
- No undocumented behaviour.