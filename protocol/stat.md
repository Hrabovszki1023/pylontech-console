# `stat`

## Status

Verified on:

- Device: Pylontech US2000C
- Main firmware: B67.5.0

## Purpose

Returns device statistics, counters, state-of-health values, cycle count, and accumulated diagnostic counters for the addressed device.

## Syntax

```text
stat
```

## Side effects

None observed.

## Response framing

A successful response was observed with:

1. `@` as payload start marker
2. one key/value entry per line
3. `Command completed successfully`
4. `$$` as payload end marker
5. `pylon_debug>` prompt after the response

## Observed response structure

Most lines use this pattern:

```text
<label> : <integer>
```

The first line is an exception:

```text
Device address           1
```

A parser must therefore not assume that every line contains a colon.

## Observed fields

| Field | Observed value type | Interpretation status |
|---|---|---|
| Device address | integer | observed |
| Data Items | integer | observed; exact meaning open |
| HisData Items | integer | observed; likely history item count |
| Charge Cnt. | integer | observed; exact counting semantics open |
| Discharge Cnt. | integer | observed; exact counting semantics open |
| Charge Times | integer | observed; unit and semantics open |
| Status Cnt. | integer | observed; exact meaning open |
| Idle Times | integer | observed; unit and semantics open |
| COC / COC2 / COCA Times | integer | observed; protection-counter semantics inferred from names only |
| DOC / DOC2 / DOCA Times | integer | observed; protection-counter semantics inferred from names only |
| SC Times | integer | observed; likely short-circuit counter |
| Bat OV/HV/LV/UV/SLP Times | integer | observed; battery-voltage-related counters inferred from names |
| Pwr OV/HV/LV/UV/SLP Times | integer | observed; pack/power-voltage-related counters inferred from names |
| COT/CUT/DOT/DUT Times | integer | observed; temperature-related counter semantics inferred from names |
| CHT/CLT/DHT/DLT Times | integer | observed; temperature-related counter semantics inferred from names |
| Shut Times | integer | observed |
| Reset Times | integer | observed |
| RV Times | integer | observed; exact meaning open |
| Input OV Times | integer | observed |
| SOH Times | integer | observed; exact meaning open |
| BMICERR Times | integer | observed; likely battery-monitor-IC error counter |
| CYCLE Times | integer | observed; likely cycle count |
| SOH | integer | observed; likely percent |
| Pwr Percent | integer | observed; likely state of charge percent |
| Pwr Coulomb | integer | observed; scale and unit open |
| Dsg Cap | integer | observed; scale and unit open |
| HT@0.5C Cnt / LT@0.5C Cnt | integer | observed; exact meaning open |
| HT Cnt / LT Cnt / LV Cnt | integer | observed; exact meaning open |
| LifeWarn Times | integer | observed |
| LifeAlarm Times | integer | observed |

## Parser contract

- Preserve unknown fields instead of discarding them.
- Parse integer values without assigning undocumented units.
- Treat unknown or newly added labels as forward-compatible data.
- Do not infer alarm state solely from a non-zero historical counter.
- Historical counters and current status must remain separate concepts.

## Example capture

See:

```text
captures/US2000C/B67.5.0/stat.txt
```

## Open questions

- Exact units for `Charge Times`, `Idle Times`, `Pwr Coulomb`, and `Dsg Cap`
- Exact meaning of the abbreviated protection counters
- Whether `CYCLE Times` is the official cycle count used by the BMS
- Whether `SOH` and `Pwr Percent` are always percentages
- Whether field order or field set changes with firmware version
