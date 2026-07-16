# ADR-001: Separate physical module identity from rack position

## Status

Accepted

## Context

Pylontech modules are addressed by their current rack position, for example `1`, `2`, `3`, and so on. This position may change after maintenance, replacement, or reordering of modules.

The command `info <position>` returns a device-specific barcode. This barcode identifies the physical module independently of its current rack position.

Using the rack position as the primary key would mix the histories of different physical modules when modules are moved.

## Decision

The barcode is used as the stable module identity and primary key for all module-specific data.

The rack position is treated only as the current topological address.

The runtime model shall therefore maintain both mappings:

```text
rack.positions[position] = barcode
modules[barcode] = module_data
```

Access by rack position is resolved through the barcode:

```text
position -> barcode -> module data
```

Direct access by barcode remains possible:

```text
barcode -> module data -> current position
```

## Discovery

The service shall discover the rack automatically. No module count or module list shall need to be configured manually.

A discovery cycle performs:

1. Execute `pwr` to determine currently present rack positions.
2. Execute `info <position>` for every present position.
3. Read the barcode and static module information.
4. Update the mapping from position to barcode.
5. Store current and historical module data under the barcode.

## Required behavior

- Moving a known module to another rack position must not create a new module history.
- A different barcode found at a known position must not overwrite the previous module's data.
- A temporarily removed module remains known by barcode and is marked as not currently present.
- A newly discovered barcode creates a new module record.
- Measurements from `pwr <position>`, `bat <position>`, `soh <position>`, and similar commands are assigned to the barcode currently mapped to that position.
- The position-to-barcode mapping must be refreshed after startup and whenever the observed rack topology changes.

## Example

Before maintenance:

```text
Position 2 -> Barcode A
Position 5 -> Barcode B
```

After maintenance:

```text
Position 2 -> Barcode B
Position 5 -> Barcode A
```

The histories remain associated with the physical modules:

```text
modules[Barcode A] -> complete history of module A
modules[Barcode B] -> complete history of module B
```

Only the current position fields and the rack mapping change.

## Consequences

### Positive

- No data confusion after maintenance or reordering.
- Automatic discovery without manual module configuration.
- Stable MQTT topics, database keys, and historical records.
- Detection of moved, removed, returned, and newly added modules.

### Constraints

- The barcode is treated as the stable unique identifier based on observed device behavior.
- Duplicate or missing barcodes must be treated as an inventory error and must not be silently merged.
- If `info <position>` fails, measurements for that position must not be assigned to an assumed previous barcode without an explicit validity rule.
