# Read-only command scope

This document defines the initial command scope for passive observation of a Pylontech battery system through the RS232 debug console.

The purpose of this scope is observability only. Version 0.1 must not change configuration, protection limits, stored data, firmware, SOC calibration, FET states, or any other battery state.

## Verified platform

The commands below were observed on:

- Model: Pylontech US2000C
- Board version: V10R04
- Main software version: B67.5.0
- Software version: V1.7
- Boot version: V2.0
- Communication version: V2.0
- Console: RS232, 115200 baud, 8N1, no flow control

Compatibility with other models or firmware versions must be verified separately.

## Version 0.1 allowlist

Only the commands in this section are allowed to be issued automatically by the first implementation.

| Command | Purpose | Verification status |
|---|---|---|
| `pwr` | Read summary data for all connected battery modules | Verified |
| `pwrsys` | Read aggregate power-system information | Verified |
| `info <position>` | Read device model, hardware version, firmware versions, cell count and serial metadata for one module | Verified |
| `pwr <position>` | Read detailed process data for one module | Verified for modules 1 to 5 |
| `bat <module>` | Read cell voltages, temperatures, current, state, SOC, coulomb value and balancing state for one module | Verified for modules 1 to 5 |

This production allowlist is intentionally identical to the initial production
allowlist in `docs/contracts/version-0.1.md`. Commands may be documented and
observed without being permitted for automatic production acquisition.

## Observability provided by the initial scope

The allowlisted commands provide the information required for a first monitoring implementation:

- battery model and firmware identification
- number of detected modules
- module voltage
- module current
- module temperature range
- module state: charge, discharge, idle or absent
- module SOC
- module SOH and cycle count
- individual cell voltages
- cell temperature groups
- minimum and maximum cell voltage
- cell voltage spread
- balancing status
- protection and shutdown counters
- BMS timestamp

## Candidate read-only commands

The following commands appear to be passive, but have not yet been verified sufficiently for inclusion in version 0.1.

| Command | Expected purpose | Status |
|---|---|---|
| `soh <addr>` | Read SOH for an addressed module | To be tested |
| `getpwr` | Read additional power information | To be tested |
| `ci` | Read current communication information | To be tested |
| `log` | Display log information | To be tested |
| `stat` | Read statistical counters, SOH, cycle count and recorded protection events | Verified, not in the version 0.1 production acquisition contract |
| `time` | Read the internal RTC value | Verified, not in the version 0.1 production acquisition contract |
| `data ...` | Read stored event or history data | Later |
| `datalist ...` | Display recorded data | Later |
| `adc` | Display ADC or address information | Later |
| `bmicrdcomm ...` | Read BMIC communication data | Later |
| `bmicrdcfg ...` | Read BMIC configuration data | Later |
| `socr`, `socsh`, `socd`, `soct` | Read SOC-related diagnostic data | Later |

A candidate command may only be promoted to the allowlist after its behaviour and response format have been captured and reviewed.

## Safety boundary

The implementation must use an explicit allowlist. It must not expose a generic production API that accepts arbitrary console commands.

The following command groups are outside the version 0.1 scope:

- `config`
- `ctrl`
- `prot`
- `shut`
- commands that clear logs, history or statistics
- EEPROM, flash and memory commands
- SOC write, calibration or reset commands
- firmware update commands
- test commands that may operate relays, MOSFETs, watchdogs, LEDs, buzzers or communication interfaces

Unknown commands and unknown firmware versions must fail closed. They must not be treated as compatible without verification.

## Next verification sequence

The next passive commands to test are:

```text
soh 1
getpwr
ci
```

For each command, store the original console response in `captures/` before defining its parsed data model.
