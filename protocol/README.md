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
