# `ci`

## Status

Verified on:

- Device: Pylontech US2000C
- Main firmware: B67.5.0

## Purpose

Returns communication counters and communication-error counters for the local device, plus selected CAN and pack-discovery information.

## Syntax

```text
ci
```

## Side effects

None observed.

## Response framing

The successful response uses the common framing:

1. echoed command,
2. `@` payload-start marker,
3. communication counters,
4. `Command completed successfully`,
5. `$$` payload-end marker,
6. next `pylon_debug>` prompt.

## Observed fields

### USART channels

Two groups were observed: `US0` and `US1`.

Each group contains:

- `Rx`
- `Tx`
- `Format`
- `Addr`
- `Ver`
- `Req`
- `LChkSum`
- `ChkSum`
- `AckErr`
- `Other`

`Rx` and `Tx` are cumulative communication counters. The remaining fields appear to be cumulative error or rejection counters, but their exact semantics are not yet verified.

In the verified capture:

- all `US0` counters were zero,
- `US1 Rx` and `US1 Tx` were non-zero,
- all observed `US1` error counters were zero.

This strongly suggests that the active internal communication path is associated with `US1`, but the physical mapping of `US0` and `US1` is not yet verified.

### CAN and pack discovery

| Field | Observed value | Preliminary interpretation |
|---|---:|---|
| `CAN Rx` | `0` | CAN receive counter |
| `CAN Tx` | `73249320` | CAN transmit counter |
| `Exist Pack Num` | `5` | Number of detected battery packs/modules |
| `Probe Pwr Addr` | `255` | Probe/broadcast address or scan state; exact meaning unknown |

## Parsing constraints

- Parse field labels independently of spacing.
- Store all counters as unsigned integers large enough for long-running cumulative values.
- Do not derive a communication fault solely from a high `Rx` or `Tx` counter.
- Treat the error counters as cumulative until proven otherwise.
- Preserve unknown fields for forward compatibility.

## Example capture

```text
captures/US2000C/B67.5.0/ci.txt
```

## Open questions

- Physical meaning and port assignment of `US0` and `US1`.
- Exact meaning of `Format`, `Addr`, `Ver`, `Req`, `LChkSum`, `ChkSum`, `AckErr`, and `Other`.
- Whether counters reset at reboot, overflow, or can be cleared by another command.
- Meaning of `Probe Pwr Addr = 255`.
