# `help`

## Status

Verified on:

- Device: Pylontech US2000C
- Board version: V10R04
- Main firmware: B67.5.0
- Software version: V1.7
- Boot version: V2.0
- Communication version: V2.0

## Purpose

Returns the command inventory exposed by the local debug console. The output is split into `Local command` and `Remote command` sections.

## Syntax

```text
help
```

The command list also advertises a parameterized form:

```text
help <command>
```

The parameterized form has not yet been verified.

## Side effects

None observed.

## Response framing

Observed successful response sequence:

1. Echoed command line
2. Start marker: `@`
3. Command inventory
4. Success line: `Command completed successfully`
5. End marker: `$$`
6. Prompt: `pylon_debug>`

## Observed structure

```text
Local command:
...
**********************************************************
Remote command:
...
Command completed successfully
$$
pylon_debug>
```

## Interpretation

### Observed

- The console distinguishes between `Local command` and `Remote command`.
- Each listed command may include a short description and an argument template.
- The list contains read-only, state-changing, destructive, diagnostic and factory-test commands.

### Inferred

- `Local command` likely refers to commands executed by the console-connected master module.
- `Remote command` likely refers to commands that can be forwarded to addressed modules.

These interpretations remain unverified.

## Safety relevance

The output is only an inventory. A command appearing in this list must not be treated as safe.

For specification version 0.1, only explicitly allowlisted passive commands may be executed automatically. Commands that write configuration, control FETs, erase memory, alter firmware, reset the device or shut it down remain excluded.

## Raw capture

See:

```text
captures/US2000C/B67.5.0/help.txt
```

## Open questions

- What does `help <command>` return?
- What is the exact semantic distinction between local and remote commands?
- Are command lists identical across models and firmware versions?
- Which remote commands require `re <addr> <command>` and which can be invoked directly?
