# Test strategy for version 0.1

## Status

Initial working version.

This strategy is intentionally not treated as final. It shall be reviewed and adjusted as implementation findings, protocol variants and operational risks become known. Changes must improve risk coverage and shall not silently reduce the acceptance criteria of the version 0.1 contract.

## Test objective

Provide sufficient evidence that the service:

- communicates reliably with the Waveshare gateway,
- parses the verified Pylontech responses correctly,
- discovers modules without manual rack configuration,
- keeps physical module identity separate from rack position,
- exposes consistent values through REST, web UI and MQTT,
- remains read-only,
- recovers from communication failures,
- can run unattended as a Docker container.

## Test levels

### 1. Parser unit tests

Use the files under `captures/` as immutable input fixtures.

Required parser coverage:

- `info <position>`,
- `pwr`,
- `pwr <position>`,
- `bat <position>`,
- `pwrsys`.

Test at least:

- correct field extraction,
- units and signed values,
- zero-based cell indices,
- missing values represented by `-`,
- variable whitespace,
- unknown additional fields,
- incomplete response without `@` or `$$`,
- failed command response,
- terminal echo and prompt outside the framed payload,
- terminal artifacts such as `<INTERRUPT>` ignored outside the payload.

### 2. Domain and discovery tests

Test the barcode-based inventory model without hardware.

Required scenarios:

- empty inventory followed by first discovery,
- new module added,
- known module removed,
- known module moved to another position,
- two modules exchange positions,
- different barcode found at an existing position,
- duplicate barcode reported at two positions,
- missing barcode,
- one module response fails while other modules remain valid,
- service restart with an existing persisted inventory.

The primary invariant is:

```text
barcode = physical identity
position = current rack topology
```

Historical data and inventory records must never be transferred from one barcode to another because a position changed.

### 3. Transport integration tests

Use a deterministic TCP test server before testing real hardware.

The test server shall simulate:

- command echo,
- framed responses using `@` and `$$`,
- delayed response chunks,
- timeout before the end marker,
- connection close during a response,
- reconnect after failure,
- malformed response,
- unsupported command response.

Verify that the command scheduler never executes two commands concurrently on one console connection.

### 4. Real-device integration tests

Run a small controlled suite against the actual Waveshare and Pylontech rack.

Verify:

- TCP connection,
- discovery of the currently connected modules,
- barcode returned by `info <position>`,
- consistency between `pwr`, `pwr <position>`, `bat <position>` and `pwrsys`,
- repeated polling over an extended period,
- recovery after temporarily disconnecting the network connection,
- no command outside the read-only allowlist is sent.

These tests must avoid state-changing console commands.

### 5. REST and web tests

Verify that REST and the web UI use the shared internal state.

REST checks:

- health state,
- rack overview,
- position-to-barcode mapping,
- module lookup by barcode,
- position lookup,
- cell values,
- stale and invalid data indicators.

Web checks:

- rack overview renders,
- all discovered modules are visible,
- correct number of cells is shown per module,
- heat-map cells include numeric values,
- outliers receive a distinguishable visual classification,
- stale values are not displayed as current,
- module detail navigation uses the barcode as stable identity.

Browser automation may later use OKW where it provides direct project value. It is not a prerequisite for starting implementation.

### 6. MQTT integration tests

Use a test MQTT broker in Docker.

Verify:

- availability topic,
- retained inventory and position mapping,
- rack topics,
- module topics under barcode IDs,
- cell topics,
- timestamps and validity,
- topology events,
- reconnect after broker interruption,
- no reassignment of historical module topics after position changes.

### 7. Container smoke tests

Verify the built Docker image:

- starts with valid configuration,
- rejects invalid required configuration,
- exposes the configured HTTP port,
- passes its health check,
- writes inventory to the mounted `/data` volume,
- retains inventory after restart,
- runs without privileged mode,
- shuts down cleanly.

## Test data

Three categories of test data are used:

1. verified real captures from the current US2000C rack,
2. deliberately modified fixtures for edge and error cases,
3. live responses from the real rack for integration acceptance.

Modified fixtures must be clearly separated from verified captures so that generated edge cases are never confused with observed device behavior.

## Automation order

Tests shall be automated in the same order as the implementation:

1. framing and transport,
2. parser tests,
3. domain and discovery,
4. REST,
5. web and heat map,
6. MQTT,
7. SQLite persistence,
8. Docker smoke tests,
9. real-device acceptance tests.

## Quality gates for version 0.1

Before release:

- all parser fixtures pass,
- discovery scenarios pass,
- no type-checking or linting errors remain,
- Docker smoke tests pass,
- REST and MQTT expose the same module identities and current positions,
- the real rack is discovered without configuring the module count,
- communication recovery is demonstrated,
- the command log contains only allowlisted read-only commands,
- all acceptance items in `docs/contracts/version-0.1.md` are verified.

## Review and adjustment

Review this strategy at least at these points:

- after the first working TCP spike,
- after all required parsers exist,
- after the first live discovery run,
- after MQTT and the heat map are operational,
- before declaring version 0.1 complete.

For each review, ask:

- Which observed failures are not covered?
- Which tests provide little useful signal?
- Which assumptions have become verified or disproved?
- Is the real hardware sufficiently represented by the fixtures?
- Are recovery and stale-data behaviors observable?
- Does any test depend unnecessarily on a fixed number or order of modules?
