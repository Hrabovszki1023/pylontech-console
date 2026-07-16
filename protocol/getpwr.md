# `getpwr`

## Status

Verified on:

- Device: Pylontech US2000C
- Board version: V10R04
- Main firmware: B67.5.0
- Software version: V1.7

## Purpose

Returns a compact, delimiter-based snapshot of one power module and its 15 cells.

The command does not include field names in the response. The current field mapping is therefore based on comparison with `pwr 1`, `bat 1`, and the observed value ranges.

## Syntax

```text
getpwr
```

## Side effects

None observed.

## Response framing

The verified successful response uses:

1. echoed command before the payload,
2. `@` as payload-start marker,
3. hash-delimited data records,
4. `Command completed successfully`,
5. `$$` as payload-end marker,
6. `pylon_debug>` as the next prompt.

## Delimiter

Each value is terminated by `#`.

Whitespace around values is formatting and must not be treated as part of the value.

## Observed structure

### Module record

The first record contains eight values:

```text
49768# -2632# 29300# 43259# Dischg# Normal# Normal# Normal#
```

Preliminary mapping:

| Position | Example | Preliminary interpretation | Confidence |
|---:|---|---|---|
| 1 | `49768` | Module voltage in mV | inferred from `pwr` |
| 2 | `-2632` | Module current in mA | inferred from `pwr` |
| 3 | `29300` | Module temperature in mC | inferred from `pwr` |
| 4 | `43259` | Coulomb/capacity value; exact unit and semantics unresolved | observed, unresolved |
| 5 | `Dischg` | Basic operating state | inferred from `pwr` |
| 6 | `Normal` | Voltage status | inferred |
| 7 | `Normal` | Current status | inferred |
| 8 | `Normal` | Temperature status | inferred |

### Cell records

The next 15 records contain four values each:

```text
3317# 26300# Normal# Normal#
```

Preliminary mapping:

| Position | Example | Preliminary interpretation | Confidence |
|---:|---|---|---|
| 1 | `3317` | Cell voltage in mV | inferred from `bat` |
| 2 | `26300` | Reported cell-associated temperature in mC | inferred from `bat` |
| 3 | `Normal` | Cell voltage status | inferred |
| 4 | `Normal` | Cell temperature status | inferred |

The 15 records correspond to cell indices `0..14` in their response order.

### Trailer records

Two single-value records follow the cell records:

```text
0#
666#
```

Their semantics are currently unknown. A parser must preserve them as unnamed trailer values rather than discarding them or assigning speculative meanings.

## Parsing constraints

- Parse values using `#` as the delimiter.
- Do not depend on line wrapping alone; the delimiter is the stronger structural marker.
- Expect one module record, 15 cell records, and two currently unnamed trailer values for the verified platform.
- Do not assign a fixed meaning to field 4 of the module record until verified.
- Preserve unknown trailer values.
- Reject incomplete responses that do not reach `$$`.
- Preserve the raw response for diagnostics.

## Example capture

See:

```text
captures/US2000C/B67.5.0/getpwr.txt
```

## Open questions

- Exact meaning and unit of module field 4 (`43259` in the verified capture).
- Meaning of the final values `0` and `666`.
- Whether the command always addresses the local/master module.
- Whether response length or field order differs on other models or firmware versions.
