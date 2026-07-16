# `info`

## Status

Verified on:

- Device: Pylontech US2000C
- Board version: V10R04
- Main firmware: B67.5.0
- Software version: V1.7
- Boot version: V2.0
- Communication version: V2.0

## Purpose

Returns static device identity, firmware, hardware and nominal specification data.

## Syntax

```text
info
```

## Side effects

None observed.

## Response framing

Observed response sequence:

1. command echo
2. `@` — start marker of the response payload
3. key-value records
4. `Command completed successfully`
5. `$$` — end marker of the response payload
6. `pylon_debug>` prompt

The start/end-marker interpretation is currently verified across the captured `help` and `info` responses. Further commands will be used to confirm that it is universal.

## Fields

| Field | Observed value | Interpretation | Type | Confidence |
|---|---:|---|---|---|
| `Device address` | `1` | Device/module address | integer | observed |
| `Manufacturer` | `Pylon` | Manufacturer identifier | string | observed |
| `Device name` | `US2000C` | Product model | string | observed |
| `Board version` | `V10R04` | Hardware/PCB revision | string | inferred |
| `Main Soft version` | `B67.5.0` | Main firmware version | string | observed |
| `Soft version` | `V1.7` | Additional software version | string | observed; semantics unresolved |
| `Boot version` | `V2.0` | Bootloader version | string | inferred |
| `Comm version` | `V2.0` | Communication firmware/protocol version | string | inferred |
| `Release Date` | `20-12-11` | Firmware or software release date | string/date | observed; date format unresolved |
| `Barcode` | redacted | Device-specific identifier | string | observed |
| `Specification` | `48V/50AH` | Nominal voltage and capacity | string | observed |
| `Cell Number` | `15` | Number of series-connected cells | integer | observed |
| `Max Dischg Curr` | `-90000mA` | Maximum discharge current | signed integer in mA | inferred from field name and unit |
| `Max Charge Curr` | `90000mA` | Maximum charge current | integer in mA | inferred from field name and unit |
| `EPONPort rate` | `1200` | EPON port data rate | integer | observed; unit/semantics unresolved |
| `Console Port rate` | `115200` | Console baud rate | integer in baud | verified by working connection |

## Parser contract

A parser for specification version 0.1 shall:

- ignore the echoed command before `@`,
- start collecting the response payload at `@`,
- stop collecting the response payload at `$$`,
- treat a missing `@` or `$$` as an incomplete or invalid response,
- accept arbitrary spacing around the colon,
- preserve unknown fields rather than discard them,
- parse current fields by removing the `mA` suffix,
- treat the barcode as sensitive device data,
- not assume a specific date format for `Release Date`,
- retain the raw response for diagnostics.

## Example capture

See [`captures/US2000C/B67.5.0/info.txt`](../captures/US2000C/B67.5.0/info.txt).

## Open questions

- Exact semantics of `Soft version` versus `Main Soft version`.
- Exact semantics of `Comm version`.
- Date format of `Release Date`.
- Whether `@` and `$$` frame every successful command response on all supported firmware versions.
