# Console captures

Store original console output here, grouped by battery model and firmware version.

Recommended layout:

```text
captures/
└── US2000C/
    └── B67.5.0/
        ├── metadata.md
        ├── help.txt
        ├── info.txt
        ├── pwr.txt
        ├── bat-1.txt
        └── stat.txt
```

## Capture rules

- Preserve spacing, line breaks, prompts, terminators and spelling errors from the device.
- Do not normalize units or convert values inside raw captures.
- Record connection settings and relevant operating conditions in `metadata.md`.
- Redact barcodes, serial numbers and private infrastructure identifiers.
- Mark redactions explicitly, for example: `<REDACTED-BARCODE>`.
- Never include credentials or access tokens.

Derived tables and interpretations belong in `../protocol/` or `../docs/`, not in raw capture files.
