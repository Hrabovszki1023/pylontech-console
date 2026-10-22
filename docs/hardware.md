# Tested hardware and compatibility

This document distinguishes hardware verified on a real battery rack from
hardware that may use a similar protocol but has not been tested.

## Verified mixed US2000/US2000C battery rack

Pylontech Console has been verified with one operational five-module rack
containing both module generations:

| Module | Quantity | Identification observed by the console |
|---|---:|---|
| Pylontech US2000 | 2 | `US2KBPL` |
| Pylontech US2000C | 3 | `US2000C` |

The mixed rack has 15 cells per module and 75 cells in total. The application
successfully verifies:

- automatic discovery of all five positions;
- stable module identity by barcode;
- rack, module-detail and all 15 per-cell measurements;
- mixed US2000 and US2000C operation in one discovered topology;
- read-only Web UI and cell-voltage heatmap;
- read-only REST API;
- publish-only MQTT integration with ioBroker.

This compatibility statement describes the observed monitoring behavior. It
does not constitute approval to combine battery models in a rack. Battery
selection, interconnection and operation must follow the Pylontech
documentation and the requirements of the complete electrical installation.

## Verified US5000 battery rack

Pylontech Console was also verified on 2026-10-22 with a standalone rack of
two new US5000 modules:

| Module | Quantity | Main firmware | Board | Cells |
|---|---:|---|---|---:|
| Pylontech US5000 | 2 | `B69.26.0.0` | `V10R04` / `NF4.E3` | 15 per module |

The real-hardware field test successfully verified:

- authenticated `pylon_debug>` console operation;
- automatic discovery of both positions and stable barcode identity;
- valid rack and module-detail acquisition;
- all 30 per-cell measurements and the Web UI heatmap;
- a valid REST health response with zero acquisition failures;
- publish-only MQTT connectivity.

The captured US5000 `pwr` response contains additional sensor-ID and system
alarm columns. Sanitized raw captures and parser regression tests are stored
under [`captures/US5000/B69.26.0.0`](../captures/US5000/B69.26.0.0/).

At the time of this compatibility test, the two-module rack was monitored as a
standalone battery rack and was not connected to the Victron system. This
statement verifies Pylontech Console monitoring compatibility, not the design
or commissioning of the power installation.

## Verified serial device server

| Component | Verified value |
|---|---|
| Device | Waveshare RS232/485/422 TO POE ETH (B) |
| Battery-side interface | RS232 |
| Network transport | transparent TCP |
| TCP port | configurable; tested with `4196` |
| Serial settings | 115200 baud, 8 data bits, no parity, 1 stop bit, no flow control |

The physical reference connections use the console port of the rack's master
module. The documented RJ45-to-DB9 cable was verified with the US2000C and
US5000 racks. See [wiring.md](wiring.md) for the pinout and the warning that
the battery console connector is not Ethernet.
See [waveshare.md](waveshare.md) for photographs, the deployment rationale and
the required network-security boundary.

## Verified deployment platform

- Docker Engine with Docker Compose;
- Proxmox-hosted dedicated Docker server;
- published container architecture: `linux/amd64`;
- optional MQTT broker provided by an ioBroker MQTT adapter.

## Not yet verified

No compatibility claim is currently made for:

- Pylontech models other than US2000, US2000C and US5000;
- racks with a cell count other than 15 cells per module;
- USB serial adapters or serial device servers other than the tested
  Waveshare model;
- container architectures other than `linux/amd64`;
- direct CAN, RS485 battery protocol or inverter communication.

Similar Pylontech products may expose related console commands, but they must
be treated as unsupported until real captures and a read-only hardware test
confirm parser and acquisition compatibility.
