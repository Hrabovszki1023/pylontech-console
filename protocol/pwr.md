# `pwr`

## Status

Verified on:

- Device: Pylontech US2000C
- Board version: V10R04
- Main firmware: B67.5.0
- Software version: V1.7

## Purpose

Returns a summary row for each supported power-module address.

The verified response contains addresses `1` through `16`. Present modules contain measurements and states. Missing modules are represented by `Base.St = Absent` and placeholder values (`-`) in the remaining columns.

## Syntax

```text
pwr
```

The command help also advertises an indexed form:

```text
pwr <index>
```

That form is not yet verified.

## Side effects

None observed.

## Response framing

The verified successful response uses:

1. echoed command before the payload,
2. `@` as payload-start marker,
3. a header line followed by module rows,
4. `Command completed successfully`,
5. `$$` as payload-end marker,
6. `pylon_debug>` as the next prompt.

This confirms the same framing previously observed for `help` and `info`.

## Columns

| Column | Observed content | Preliminary interpretation | Confidence |
|---|---|---|---|
| `Power` | Integer `1..16` | Module/power address | observed |
| `Volt` | Example `49726` | Module voltage; likely mV | inferred |
| `Curr` | Example `-3037` | Module current; likely mA; negative observed while discharging | inferred |
| `Tempr` | Example `29300` | Module temperature; likely milli-degrees Celsius | inferred |
| `Tlow` | Example `26000` | Lowest reported temperature; likely milli-degrees Celsius | inferred |
| `Thigh` | Example `26600` | Highest reported temperature; likely milli-degrees Celsius | inferred |
| `Vlow` | Example `3315` | Lowest cell voltage; likely mV | inferred |
| `Vhigh` | Example `3316` | Highest cell voltage; likely mV | inferred |
| `Base.St` | `Dischg`, `Absent` | Base operating state | observed |
| `Volt.St` | `Normal` | Voltage state | observed |
| `Curr.St` | `Normal` | Current state | observed |
| `Temp.St` | `Normal` | Temperature state | observed |
| `Coulomb` | `95%`, `96%` | State of charge percentage | inferred |
| `Time` | `YYYY-MM-DD hh:mm:ss` | Per-module timestamp | observed |
| `B.V.St` | `Normal` | Battery-voltage state | observed, semantics not yet resolved |
| `B.T.St` | `Normal` | Battery-temperature state | observed, semantics not yet resolved |
| `MosTempr` | Numeric or `-` | MOSFET temperature; likely milli-degrees Celsius | inferred |
| `M.T.St` | `Normal` or `-` | MOSFET-temperature state | inferred |

## Present and absent modules

In the verified capture:

- addresses `1..5` were present,
- addresses `6..16` were absent,
- absent rows used `Absent` in `Base.St`,
- other unavailable values were represented by `-`.

A parser must not coerce `-` to numeric zero. It must represent the value as unavailable/null.

## Parsing constraints

- Parse rows by the fixed header order, not by assuming that all whitespace-delimited fields have the same width.
- The `Time` field contains both date and time and therefore two whitespace-delimited tokens.
- Accept numeric and placeholder (`-`) values where observed.
- Treat unknown state strings as valid unknown enum values rather than silently mapping them to `Normal` or another known state.
- Do not infer the number of installed modules solely from the highest returned address; count rows whose `Base.St` is not `Absent`.
- Preserve the raw response for diagnostics when parsing fails.

## Example capture

See:

```text
captures/US2000C/B67.5.0/pwr.txt
```

## Open questions

- Exact units and scaling for `Volt`, `Curr`, temperatures, `Vlow`, `Vhigh`, and `MosTempr`.
- Complete enum sets for all state columns.
- Semantics of `B.V.St`, `B.T.St`, and `M.T.St`.
- Whether the address range is always `1..16` on other models and firmware versions.
- Behavior and output format of `pwr <index>`.
