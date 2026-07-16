# Pylontech Console

Open documentation and reference implementations for the undocumented Pylontech RS232 debug console.

The project documents the electrical connection, serial transport, console commands and response formats used by Pylontech battery modules. The initial reference setup uses a Pylontech US2000C and a Waveshare RS232/485/422-to-PoE-Ethernet serial server.

## Goals

- document the RS232 console interface and its pinout;
- preserve unmodified console captures for different models and firmware versions;
- specify commands and response formats independently of a programming language;
- provide reusable parsers and integrations for monitoring systems;
- expose module, cell, temperature, state and diagnostic data without a vendor cloud.

## Current status

The following commands have been verified on a Pylontech US2000C with main firmware `B67.5.0`:

- `help`
- `info`
- `pwr`
- `bat <module>`
- `stat`
- `time`

The console was accessed successfully through transparent RS232-over-TCP at `115200 8N1`.

## Reference architecture

```text
Pylontech Console Port
        │ RS232
        ▼
Waveshare Serial Server
        │ Ethernet / TCP
        ▼
Terminal, ioBroker or another client
```

## Repository structure

```text
docs/       Hardware, wiring, transport and operating documentation
protocol/   Command specifications and response formats
captures/   Unmodified console output grouped by model and firmware
examples/   Reproducible connection and integration examples
```

## Safety

The debug console exposes read and write commands. Some commands can alter protection thresholds, switch charge or discharge paths, reset counters or change persistent configuration.

Do not execute undocumented write commands on a battery connected to a live system. Test potentially destructive commands only on an isolated module and verify the electrical state independently.

This project is independent and is not affiliated with or endorsed by Pylon Technologies Co., Ltd. Use all information at your own risk.

## Data hygiene

Before committing captures, remove or replace:

- battery barcodes and serial numbers;
- private IP addresses where disclosure is unwanted;
- usernames, hostnames and other personal infrastructure details.

Measured values and firmware identifiers should remain unchanged whenever possible because they are required for reproducible protocol analysis.

## Roadmap

1. Document the verified hardware setup and cable pinout.
2. Add raw captures for the verified console commands.
3. Define command and response contracts.
4. Implement parsers with recorded-response tests.
5. Add MQTT, ioBroker and Modbus TCP integrations.

## Contributions

Reports from other Pylontech models and firmware versions are welcome. Please include the exact model, firmware versions, transport settings and an unmodified console capture with sensitive identifiers redacted.
