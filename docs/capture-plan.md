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
- [x] info
- [x] pwr
- [x] bat 1
- [x] bat 2
- [x] bat 3
- [x] bat 4
- [x] bat 5
- [x] stat
- [x] time

## Phase 2 - Extended Observation

- [x] pwr 1
- [x] pwr 2
- [x] pwr 3
- [x] pwr 4
- [x] pwr 5
- [x] getpwr
- [x] pwrsys
- [x] ci
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
