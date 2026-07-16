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

The command supports both the locally attached module and an explicitly addressed module in the stack.

## Syntax

Local module:

```text
info
```

Explicit module address:

```text
info <address>
```

Verified example:

```text
info 2
```

The tested firmware did **not** support forwarding this request through:

```text
re 2 info
```

It returned `This version do not support this command!`. Therefore, indexed `info <address>` is the supported mechanism on the verified firmware.

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

## Fields

| Field | Observed value | Interpretation | Type | Confidence |
|---|---:|---|---|---|
| `Device address` | `1`, `2` | Current logical module address in the stack | integer | verified |
| `Manufacturer` | `Pylon` | Manufacturer identifier | string | observed |
| `Device name` | `US2000C` | Product model | string | observed |
| `Board version` | `V10R04` | Hardware/PCB revision | string | inferred |
| `Main Soft version` | `B67.5.0` | Main firmware version | string | observed |
| `Soft version` | `V1.7` | Additional software version | string | observed; semantics unresolved |
| `Boot version` | `V2.0` | Bootloader version | string | inferred |
| `Comm version` | `V2.0` | Communication firmware/protocol version | string | inferred |
| `Release Date` | `20-12-11` | Firmware or software release date | string/date | observed; date format unresolved |
| `Barcode` | device-specific value | Stable physical module identifier | string | strongly supported |
| `Specification` | `48V/50AH` | Nominal voltage and capacity | string | observed |
| `Cell Number` | `15` | Number of series-connected cells | integer | observed |
| `Max Dischg Curr` | `-90000mA` | Maximum discharge current | signed integer in mA | inferred from field name and unit |
| `Max Charge Curr` | `90000mA` | Maximum charge current | integer in mA | inferred from field name and unit |
| `EPONPort rate` | `1200` | EPON port data rate | integer | observed; unit/semantics unresolved |
| `Console Port rate` | `115200` | Console baud rate | integer in baud | verified by working connection |

## Dynamic module discovery and identity

A service shall not require a configured module count or fixed address list.

Recommended discovery sequence:

1. Run `pwr` and select all rows whose `Base.St` is not `Absent`.
2. For each discovered address, run `info <address>`.
3. Use `Device address` as the current runtime position.
4. Use `Barcode` as the stable physical module identifier.

This allows the service to recognize the same physical module after modules are reordered in the stack.

The internal model must therefore keep these values separate:

```text
address   = current logical position in the stack
module_id = stable physical identity, derived from Barcode
```

A changed address with an unchanged barcode represents a moved module, not a new module.

## Parser contract

A parser for specification version 0.1 shall:

- ignore the echoed command before `@`,
- start collecting the response payload at `@`,
- stop collecting the response payload at `$$`,
- treat a missing `@` or `$$` as an incomplete or invalid response,
- accept arbitrary spacing around the colon,
- preserve unknown fields rather than discard them,
- parse current fields by removing the `mA` suffix,
- treat the barcode as device identity and potentially sensitive device data,
- not assume a specific date format for `Release Date`,
- retain the raw response for diagnostics,
- support both `info` and `info <address>`,
- reject an indexed response when its returned `Device address` does not match the requested address.

## Example captures

- [`captures/US2000C/B67.5.0/info.txt`](../captures/US2000C/B67.5.0/info.txt)
- [`captures/US2000C/B67.5.0/info-2.txt`](../captures/US2000C/B67.5.0/info-2.txt)

## Open questions

- Exact semantics of `Soft version` versus `Main Soft version`.
- Exact semantics of `Comm version`.
- Date format of `Release Date`.
- Whether indexed `info <address>` is supported on other models and firmware versions.
- Whether the barcode is guaranteed unique across all Pylontech module families.
