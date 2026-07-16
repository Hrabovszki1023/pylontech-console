# `pwrsys`

## Status

Verified on:

- Device: Pylontech US2000C
- Board version: V10R04
- Main firmware: B67.5.0
- Software version: V1.7

## Purpose

Returns aggregate information for the complete Pylontech power system.

## Syntax

```text
pwrsys
```

## Side effects

None observed.

## Response framing

The verified successful response uses the common console framing:

1. echoed command,
2. `@` as payload-start marker,
3. payload,
4. `Command completed successfully`,
5. `$$` as payload-end marker,
6. `pylon_debug>` as the next prompt.

## Observed fields

| Field | Unit | Preliminary interpretation | Confidence |
|---|---:|---|---|
| `System is discharging` | - | System operating state | observed |
| `Total Num` | count | Configured/known module count | inferred |
| `Present Num` | count | Currently present module count | inferred |
| `Sleep Num` | count | Sleeping module count | inferred |
| `System Volt` | mV | System voltage | observed |
| `System Curr` | mA | Aggregated system current | observed |
| `System RC` | mAH | Remaining capacity | inferred |
| `System FCC` | mAH | Full-charge capacity | inferred |
| `System SOC` | % | System state of charge | observed |
| `System SOH` | % | System state of health | observed |
| `Highest voltage` | mV | Highest cell voltage across present modules | inferred |
| `Average voltage` | mV | Average cell voltage across present modules | inferred |
| `Lowest voltage` | mV | Lowest cell voltage across present modules | inferred |
| `Highest temperature` | mC | Highest reported battery temperature | inferred |
| `Average temperature` | mC | Average reported battery temperature | inferred |
| `Lowest temperature` | mC | Lowest reported battery temperature | inferred |
| `Recommend chg voltage` | mV | Per-module recommended charge voltage | inferred |
| `Recommend dsg voltage` | mV | Per-module recommended discharge voltage | inferred |
| `Recommend chg current` | mA | Per-module recommended charge current | inferred |
| `Recommend dsg current` | mA | Per-module recommended discharge current | inferred |
| `system Recommend chg voltage` | mV | System-level recommended charge voltage | inferred |
| `system Recommend dsg voltage` | mV | System-level recommended discharge voltage | inferred |
| `system Recommend chg current` | mA | System-level recommended charge current | inferred |
| `system Recommend dsg current` | mA | System-level recommended discharge current | inferred |

## Important observation

In the verified capture, five modules were present. The system-level recommended currents were exactly five times the corresponding per-module recommended currents:

- charge: `10000 mA` per module and `50000 mA` for the system,
- discharge: `-25000 mA` per module and `-125000 mA` for the system.

This supports, but does not yet prove for all firmware versions, that the system current recommendations are aggregated across present modules.

## Parsing constraints

- Parse the state sentence separately from the subsequent key/value lines.
- Field labels contain spaces and inconsistent capitalization; parse by the colon separator rather than whitespace token positions.
- Preserve unknown fields for forward compatibility.
- Preserve the sign of current values.
- Normalize units only after successful parsing; retain raw values for diagnostics.
- Do not assume `Total Num` and `Present Num` are always equal.

## Example capture

See:

```text
captures/US2000C/B67.5.0/pwrsys.txt
```

## Open questions

- Exact definitions of `RC` and `FCC`.
- Whether voltage and temperature extrema cover cells, sensors, modules, or another aggregation level.
- Difference between the four `Recommend ...` fields and the four `system Recommend ...` fields beyond the observed current aggregation.
- Possible additional system-state sentences for charging, idle, sleeping, warning, or fault states.
