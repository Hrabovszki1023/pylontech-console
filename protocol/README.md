# Protocol specification

This directory defines the observable contract of the Pylontech debug console.

Each command specification should contain:

1. command name and purpose;
2. verified syntax and parameter ranges;
3. read-only or state-changing classification;
4. request framing and line endings;
5. success and failure terminators;
6. field names, units and scaling;
7. indexing rules;
8. verified models and firmware versions;
9. raw-capture references;
10. known ambiguities and open questions.

Initially verified commands:

- `help`
- `info`
- `pwr`
- `bat <module>`
- `stat`
- `time`

A command must not be described as safe or read-only solely because its name appears harmless. Classification must be based on observed behavior or reliable documentation.

## Parser input boundary

Command specifications and stored captures document the complete observed
console exchange, including command echo, framing markers and the following
prompt. This does not make those elements part of command-specific parser
input.

The framing layer owns:

- ignoring command echo and prompt text outside a response,
- recognizing `@` as the response start marker,
- recognizing `$$` as the response end marker,
- rejecting incomplete responses,
- removing the framing markers and adjacent line endings.

Command-specific parsers receive only the complete payload returned by the
framing layer. Parser input therefore excludes command echo, prompt, `@` and
`$$`, but includes the protocol confirmation line:

```text
Command completed successfully
```

Each command-specific parser validates that confirmation according to its
command contract. Framing behavior and incomplete-marker cases remain tests of
the framing layer rather than command-specific parser tests.
