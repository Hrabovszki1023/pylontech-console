# `bat`

## Status

Verified on:

- Device: Pylontech US2000C
- Main firmware: B67.5.0

## Purpose

Returns per-cell data for one addressed battery module.

## Syntax

```text
bat <module>
```

Observed valid module index:

```text
bat 1
```

## Side effects

None observed.

## Response framing

A successful response is framed as follows:

```text
<command echo>
@
<payload>
Command completed successfully
$$
pylon_debug>
```

Observed interpretation:

- `@` marks the beginning of the response payload.
- `$$` marks the end of the response payload.
- `pylon_debug>` is the next prompt and is not part of the payload.

## Response table

Observed columns:

| Column | Observed value type | Current interpretation | Confidence |
|---|---|---|---|
| `Battery` | integer | zero-based cell index | observed/inferred |
| `Volt` | integer | cell voltage, probably mV | inferred |
| `Curr` | signed integer | module current, repeated per row, probably mA | inferred |
| `Tempr` | integer | temperature, probably milli-degrees Celsius | inferred |
| `Base State` | text | module operating state | observed |
| `Volt. State` | text | voltage status | observed |
| `Curr. State` | text | current status | observed |
| `Temp. State` | text | temperature status | observed |
| `SOC` | percentage text | state of charge | observed |
| `Coulomb` | integer plus `mAH` | charge quantity associated with the row | observed; exact semantics open |
| `BAL` | text | balancing flag (`Y`/`N` expected) | observed/inferred |

## Row count

For the tested US2000C, the response contains 15 rows indexed from `0` through `14`.

This matches the `Cell Number : 15` value returned by `info`.

## Parser requirements

- Do not convert the `Battery` field to a one-based index inside the protocol parser.
- Preserve the original zero-based index from the console.
- Parse `SOC` by removing the trailing `%` only after retaining the raw value.
- Parse `Coulomb` as a numeric value plus explicit unit.
- Treat repeated current values as observed row data; aggregation semantics belong to a higher layer.
- Do not assume that all rows are sampled atomically. Values may change while the table is being emitted.
- Preserve unknown status strings rather than mapping them silently to `Normal` or another default.

## Derived observability values

A consumer may derive:

- minimum cell voltage,
- maximum cell voltage,
- cell-voltage spread,
- index of the minimum-voltage cell,
- index of the maximum-voltage cell,
- balancing cell count,
- minimum and maximum reported temperature.

These derived values are not returned directly by the command.

## Example

See:

```text
captures/US2000C/B67.5.0/bat-1.txt
```

## Open questions

- Are `Volt`, `Curr`, and `Tempr` units identical across all supported models and firmware versions?
- Is `Coulomb` genuinely cell-specific, or is it a repeated module-level value with small internal per-channel differences?
- Which exact values can appear in `BAL`?
- What error response is returned for an absent module index?
