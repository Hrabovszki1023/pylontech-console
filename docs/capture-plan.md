# Capture Plan

This document defines the capture sequence for the initial protocol specification.

## Rules

- Only passive (read-only) commands.
- Store complete terminal output.
- Do not modify formatting.
- Anonymize serial numbers/barcodes if necessary.
- One capture file per command.

## Phase 1 - Core Commands

- [x] help
- [ ] info
- [ ] pwr
- [ ] bat 1
- [ ] bat 2
- [ ] bat 3
- [ ] bat 4
- [ ] bat 5
- [ ] stat
- [ ] time

## Phase 2 - Extended Observation

- [ ] pwr 1
- [ ] pwr 2
- [ ] pwr 3
- [ ] pwr 4
- [ ] pwr 5
- [ ] getpwr
- [ ] pwrsys
- [ ] ci
- [ ] soh 1
- [ ] soh 2
- [ ] soh 3
- [ ] soh 4
- [ ] soh 5

## Phase 3 - Diagnostic Read Commands

- [ ] adc
- [ ] log
- [ ] data history
- [ ] datalist history
- [ ] socr
- [ ] socsh
- [ ] socd
- [ ] soct
- [ ] bmicrdcfg
- [ ] bmicrdcomm

## Deferred

Commands that modify device state are intentionally excluded from this specification version.
