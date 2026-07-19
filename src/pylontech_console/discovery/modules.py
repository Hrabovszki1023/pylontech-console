from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Protocol

from pylontech_console.domain.discovery import (
    DiscoveryError,
    DiscoveryErrorKind,
    DiscoveryResult,
    InventoryState,
    ModuleRecord,
    TopologyEvent,
    TopologyEventKind,
)
from pylontech_console.domain.info import ModuleIdentity
from pylontech_console.domain.pwr import PwrPosition, PwrSummary


class ModuleIdentityReader(Protocol):
    async def read_identity(self, position: int) -> ModuleIdentity: ...


class DiscoveryInputError(ValueError):
    def __init__(self, kind: DiscoveryErrorKind, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind


@dataclass(frozen=True)
class _Candidate:
    power: PwrPosition
    identity: ModuleIdentity
    barcode: str


def _utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DiscoveryInputError(
            DiscoveryErrorKind.INVALID_TIMESTAMP,
            f"{field_name} must be timezone-aware",
        )
    return value.astimezone(timezone.utc)


def _inventory_error_event(
    timestamp: datetime,
    error: DiscoveryError,
) -> TopologyEvent:
    return TopologyEvent(
        kind=TopologyEventKind.INVENTORY_ERROR,
        timestamp=timestamp,
        detail=error.detail,
        barcode=error.barcode,
        position=error.position,
    )


def _validate_input(pwr_summary: PwrSummary) -> datetime:
    observed_at = _utc(pwr_summary.received_at, "pwr_summary.received_at")
    positions = [position.position for position in pwr_summary.positions]
    if len(positions) != len(set(positions)):
        raise DiscoveryInputError(
            DiscoveryErrorKind.INCONSISTENT_INPUT,
            "pwr_summary contains duplicate positions",
        )
    return observed_at


async def _read_candidates(
    pwr_summary: PwrSummary,
    identity_reader: ModuleIdentityReader,
) -> tuple[list[_Candidate], dict[int, DiscoveryError]]:
    candidates: list[_Candidate] = []
    errors: dict[int, DiscoveryError] = {}

    for power in pwr_summary.positions:
        if not power.present:
            continue
        try:
            identity = await identity_reader.read_identity(power.position)
        except Exception:
            errors[power.position] = DiscoveryError(
                kind=DiscoveryErrorKind.IDENTITY_READ_FAILED,
                detail="module identity read failed",
                position=power.position,
            )
            continue

        if identity.position != power.position:
            errors[power.position] = DiscoveryError(
                kind=DiscoveryErrorKind.POSITION_MISMATCH,
                detail="returned module position does not match request",
                position=power.position,
            )
            continue

        barcode = identity.barcode.strip()
        if not barcode:
            errors[power.position] = DiscoveryError(
                kind=DiscoveryErrorKind.MISSING_BARCODE,
                detail="module identity has no barcode",
                position=power.position,
            )
            continue

        try:
            received_at = _utc(identity.received_at, "identity.received_at")
        except DiscoveryInputError:
            errors[power.position] = DiscoveryError(
                kind=DiscoveryErrorKind.INVALID_TIMESTAMP,
                detail="module identity timestamp must be timezone-aware",
                position=power.position,
                barcode=barcode,
            )
            continue

        candidates.append(
            _Candidate(
                power=power,
                identity=replace(
                    identity,
                    received_at=received_at,
                    barcode=barcode,
                ),
                barcode=barcode,
            ),
        )

    duplicate_barcodes = {
        barcode
        for barcode, count in Counter(
            candidate.barcode for candidate in candidates
        ).items()
        if count > 1
    }
    if duplicate_barcodes:
        unique_candidates: list[_Candidate] = []
        for candidate in candidates:
            if candidate.barcode in duplicate_barcodes:
                errors[candidate.power.position] = DiscoveryError(
                    kind=DiscoveryErrorKind.DUPLICATE_BARCODE,
                    detail="barcode was returned for multiple positions",
                    position=candidate.power.position,
                    barcode=candidate.barcode,
                )
            else:
                unique_candidates.append(candidate)
        candidates = unique_candidates

    return candidates, errors


def _topology_events_for_candidate(
    candidate: _Candidate,
    previous: InventoryState,
    observed_at: datetime,
) -> tuple[list[TopologyEvent], str | None]:
    events: list[TopologyEvent] = []
    previous_record = previous.modules.get(candidate.barcode)
    previous_occupant = previous.positions.get(candidate.power.position)

    if previous_record is None:
        events.append(
            TopologyEvent(
                kind=TopologyEventKind.MODULE_DISCOVERED,
                timestamp=observed_at,
                detail="new module identity discovered",
                barcode=candidate.barcode,
                position=candidate.power.position,
            ),
        )
    elif previous_record.present is not True:
        events.append(
            TopologyEvent(
                kind=TopologyEventKind.MODULE_REAPPEARED,
                timestamp=observed_at,
                detail="known module identity reappeared",
                barcode=candidate.barcode,
                position=candidate.power.position,
                previous_position=previous_record.current_position,
            ),
        )
    elif previous_record.current_position != candidate.power.position:
        events.append(
            TopologyEvent(
                kind=TopologyEventKind.MODULE_MOVED,
                timestamp=observed_at,
                detail="known module identity changed position",
                barcode=candidate.barcode,
                position=candidate.power.position,
                previous_position=previous_record.current_position,
            ),
        )

    replaced_barcode: str | None = None
    incoming_was_present = (
        previous_record is not None and previous_record.present is True
    )
    if (
        previous_occupant is not None
        and previous_occupant != candidate.barcode
        and not incoming_was_present
    ):
        replaced_barcode = previous_occupant
        events.append(
            TopologyEvent(
                kind=TopologyEventKind.MODULE_REPLACED_AT_POSITION,
                timestamp=observed_at,
                detail="different module identity occupies known position",
                barcode=candidate.barcode,
                position=candidate.power.position,
                replaced_barcode=previous_occupant,
            ),
        )

    return events, replaced_barcode


def _reconcile(
    pwr_summary: PwrSummary,
    previous: InventoryState,
    candidates: list[_Candidate],
    errors_by_position: dict[int, DiscoveryError],
    observed_at: datetime,
) -> DiscoveryResult:
    positions = {candidate.power.position: candidate.barcode for candidate in candidates}
    modules = dict(previous.modules)
    events: list[TopologyEvent] = []
    replaced_barcodes: set[str] = set()

    for candidate in candidates:
        previous_record = previous.modules.get(candidate.barcode)
        candidate_events, replaced_barcode = _topology_events_for_candidate(
            candidate,
            previous,
            observed_at,
        )
        events.extend(candidate_events)
        if replaced_barcode is not None:
            replaced_barcodes.add(replaced_barcode)

        seen_at = candidate.identity.received_at
        modules[candidate.barcode] = ModuleRecord(
            barcode=candidate.barcode,
            identity=candidate.identity,
            current_position=candidate.power.position,
            present=True,
            first_seen_at=(
                seen_at
                if previous_record is None
                else previous_record.first_seen_at
            ),
            last_seen_at=seen_at,
            power=candidate.power,
        )

    unresolved_positions = set(errors_by_position)
    current_barcodes = set(positions.values())
    for barcode, previous_record in previous.modules.items():
        if barcode in current_barcodes:
            continue
        was_unresolved = (
            previous_record.current_position is not None
            and previous_record.current_position in unresolved_positions
        )
        modules[barcode] = replace(
            previous_record,
            current_position=None,
            present=None if was_unresolved else False,
            power=None,
        )
        if (
            previous_record.present is True
            and not was_unresolved
            and barcode not in replaced_barcodes
        ):
            events.append(
                TopologyEvent(
                    kind=TopologyEventKind.MODULE_REMOVED,
                    timestamp=observed_at,
                    detail="known module identity is no longer present",
                    barcode=barcode,
                    previous_position=previous_record.current_position,
                ),
            )

    errors = tuple(
        errors_by_position[position.position]
        for position in pwr_summary.positions
        if position.position in errors_by_position
    )
    events.extend(
        _inventory_error_event(observed_at, error) for error in errors
    )

    return DiscoveryResult(
        state=InventoryState(
            observed_at=observed_at,
            positions=MappingProxyType(positions),
            modules=MappingProxyType(modules),
        ),
        events=tuple(events),
        errors=errors,
    )


async def discover_modules(
    pwr_summary: PwrSummary,
    previous: InventoryState,
    identity_reader: ModuleIdentityReader,
) -> DiscoveryResult:
    """Resolve present rack positions and reconcile barcode-keyed inventory."""

    observed_at = _validate_input(pwr_summary)
    candidates, errors = await _read_candidates(pwr_summary, identity_reader)
    return _reconcile(
        pwr_summary,
        previous,
        candidates,
        errors,
        observed_at,
    )
