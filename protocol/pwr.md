# `pwr`

## Status

Verified on:

- Device: Pylontech US2000C
- Board version: V10R04
- Main firmware: B67.5.0
- Software version: V1.7

## Purpose

The command supports two verified forms:

- `pwr` returns a summary row for each supported power-module address.
- `pwr <index>` returns a detailed key/value view for one module.

## Syntax

```text
pwr
pwr <index>
```

Verified indexed example:

```text
pwr 1
```

## Side effects

None observed.

## Response framing

Both verified forms use:

1. echoed command before the payload,
2. `@` as payload-start marker,
3. command-specific payload,
4. `Command completed successfully`,
5. `$$` as payload-end marker,
6. `pylon_debug>` as the next prompt.

## Unindexed response: `pwr`

The verified response contains addresses `1` through `16`. Present modules contain measurements and states. Missing modules are represented by `Base.St = Absent` and placeholder values (`-`) in the remaining columns.

### Columns

| Column | Observed content | Preliminary interpretation | Confidence |
|---|---|---|---|
| `Power` | Integer `1..16` | Module/power address | observed |
| `Volt` | Example `49726` | Module voltage in mV | verified by indexed response |
| `Curr` | Example `-3037` | Module current in mA; negative observed while discharging | verified by indexed response |
| `Tempr` | Example `29300` | Module temperature in milli-degrees Celsius (`mC`) | verified by indexed response |
| `Tlow` | Example `26000` | Lowest reported temperature; likely `mC` | inferred |
| `Thigh` | Example `26600` | Highest reported temperature; likely `mC` | inferred |
| `Vlow` | Example `3315` | Lowest cell voltage; likely mV | inferred |
| `Vhigh` | Example `3316` | Highest cell voltage; likely mV | inferred |
| `Base.St` | `Dischg`, `Absent` | Base operating state | observed |
| `Volt.St` | `Normal` | Voltage state | observed |
| `Curr.St` | `Normal` | Current state | observed |
| `Temp.St` | `Normal` | Temperature state | observed |
| `Coulomb` | `95%`, `96%` | State of charge percentage | confirmed by indexed `Coulomb` field |
| `Time` | `YYYY-MM-DD hh:mm:ss` | Per-module timestamp | observed |
| `B.V.St` | `Normal` | Battery-voltage state | observed, semantics unresolved |
| `B.T.St` | `Normal` | Battery-temperature state | observed, semantics unresolved |
| `MosTempr` | Numeric or `-` | MOSFET temperature; likely `mC` | inferred |
| `M.T.St` | `Normal` or `-` | MOSFET-temperature state | inferred |

### Present and absent modules

In the verified capture:

- addresses `1..5` were present,
- addresses `6..16` were absent,
- absent rows used `Absent` in `Base.St`,
- other unavailable values were represented by `-`.

A parser must not coerce `-` to numeric zero. It must represent the value as unavailable/null.

## Indexed response: `pwr <index>`

The indexed form returns a separator-delimited key/value block for one module rather than the summary table.

### Verified fields

| Field | Example | Unit/type | Confidence |
|---|---:|---|---|
| `Power` | `1` | module address | observed |
| `Voltage` | `49769` | `mV` | observed |
| `Current` | `-2185` | `mA` | observed |
| `Temperature` | `29300` | `mC` | observed |
| `Coulomb` | `94` | `%` | observed |
| `Total Coulomb` | `50000` | `mAH` | observed; exact semantics unresolved |
| `Max Voltage` | `54000` | `mV` | observed; exact semantics unresolved |
| `Charge Times` | `26076` | integer counter/value | observed; semantics unresolved |
| `Basic Status` | `Dischg` | state string | observed |
| `Charge Sec.` | `1306` | `s` | observed while `Basic Status` is `Charge` |
| `Discharge Sec.` | `3320` | `s` | observed while `Basic Status` is `Dischg` |
| `Volt Status` | `Normal` | state string | observed |
| `Current Status` | `Normal` | state string | observed |
| `Tmpr. Status` | `Normal` | state string | observed |
| `Coul. Status` | `Normal` | state string | observed |
| `Soh. Status` | `Normal` | state string | observed |
| `Heater Status` | `OFF` | state string | observed |
| `Protect ENA` | list of protection identifiers | whitespace-separated identifiers | observed |
| `Bat Events` | `0x0` | hexadecimal bit field | observed |
| `Power Events` | `0x0` | hexadecimal bit field | observed |
| `System Fault` | `0x0` | hexadecimal bit field | observed |

### Indexed parsing constraints

- Parse the module address from the `Power` heading.
- Parse field names and values around the first colon.
- Preserve the displayed unit separately from the numeric value.
- `Protect ENA` is a variable-length list and must not be parsed as a single enum.
- Event and fault fields are hexadecimal bit fields. Preserve both the raw text and parsed integer representation.
- `Charge Sec.` and `Discharge Sec.` are optional, state-dependent fields. Parse
  either field when present, but do not require either one because other operating
  states may omit both.
- Unknown fields must be retained instead of discarded.
- Do not assume that all firmware versions return the same field set or order.

## General parsing constraints

- For the unindexed table, parse rows by the fixed header order.
- The `Time` field contains two whitespace-delimited tokens.
- Accept numeric and placeholder (`-`) values where observed.
- Treat unknown state strings as valid unknown enum values.
- Determine installed module count from rows whose `Base.St` is not `Absent`.
- Preserve raw responses for diagnostics when parsing fails.

## Example captures

```text
captures/US2000C/B67.5.0/pwr.txt
captures/US2000C/B67.5.0/pwr-1.txt
```

## Open questions

- Exact semantics of `Total Coulomb`, `Max Voltage`, `Charge Times`,
  `Charge Sec.`, and `Discharge Sec.`.
- Complete enum sets for all status fields.
- Meaning and bit allocation of `Bat Events`, `Power Events`, and `System Fault`.
- Semantics of `B.V.St`, `B.T.St`, and `M.T.St` in the summary response.
- Whether the address range is always `1..16` on other models and firmware versions.
- Behavior for an absent or invalid index.
