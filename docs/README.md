# Documentation

This directory contains the technical documentation for connecting to and operating the Pylontech debug console.

Available documents:

- `hardware.md` — verified modules, deployment platform and explicit
  compatibility limits;
- `wiring.md` — RJ45 console and DB9 pinout;
- `waveshare.md` — verified RS232-over-TCP device, installation photographs,
  deployment rationale and network-security boundary;

Planned documents:

- `console-access.md` — terminal settings and connection test;
- `architecture.md` — integration with ioBroker, MQTT and Modbus TCP;
- `safety.md` — operational boundaries for read and write commands.

The protocol contract itself belongs in `../protocol/`. Original command output belongs in `../captures/`.
