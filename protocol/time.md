# `time`

## Status

Verified on:

- Device: Pylontech US2000C
- Main firmware: B67.5.0

## Purpose

Returns the battery management system real-time clock and a test result.

## Syntax

```text
time
```

The help output also lists an argument form:

```text
time [year] [month] [day] [hour] [minute] [second]
```

Only the argument-free, read-only form is part of specification version 0.1. The parameterized form may modify the clock and is therefore excluded.

## Side effects

None observed for the argument-free form.

## Response framing

```text
@
<payload>
Command completed successfully
$$
```

## Observed fields

| Field | Example | Interpretation | Confidence |
|---|---|---|---|
| `RTC` | `2026-07-17 01:40:48` | BMS real-time clock value | observed |
| `Test result` | `pass` | Result of the RTC self-test/read operation | observed |

## Parser requirements

- Parse the `RTC` value as a local device timestamp without assuming a timezone.
- Preserve the original timestamp string.
- Treat `Test result:pass` as a separate field, not as proof that the RTC time is correct.
- A parser must not invoke the parameterized `time` form in normal observation mode.

## Example

See [`../captures/US2000C/B67.5.0/time.txt`](../captures/US2000C/B67.5.0/time.txt).

## Open questions

- Which timezone, if any, the RTC represents.
- Whether the clock is synchronized by another interface or must be maintained manually.
- Behavior of the parameterized form is intentionally not tested in the read-only specification.
