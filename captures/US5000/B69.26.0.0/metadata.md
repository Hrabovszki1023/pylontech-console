# US5000 B69.26.0.0 captures

These sanitized captures were recorded from a two-module Pylontech US5000
rack on 2026-10-12.

## Devices

- Model: Pylontech US5000
- Quantity: 2
- Board version: `V10R04`
- Board: `NF4.E3`
- Main software: `B69.26.0.0`
- Software: `V2.3`
- Boot version: `V1.0`
- Communication version: `V2.0`
- Specification: `48V/100AH`
- Cell count: 15 per module

## Capture state

- Both modules were present at positions 1 and 2.
- Both modules reported 60% SOC and zero current.
- The console was authenticated in `pylon_debug>` mode.
- Barcodes were replaced with explicit redaction markers before committing.

## Files

- `info-1.txt` and `info-2.txt`: module identity responses
- `pwr.txt`: rack inventory summary with the extended US5000 columns
- `bat-1.txt` and `bat-2.txt`: 15 cell measurements per module

The raw spacing, prompts, terminators, and device spelling are intentionally
preserved.
