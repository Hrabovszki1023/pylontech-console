import asyncio
from datetime import datetime, timedelta, timezone
from typing import Mapping

import pytest

from pylontech_console.discovery import DiscoveryInputError, discover_modules
from pylontech_console.domain.discovery import (
    DiscoveryErrorKind,
    DiscoveryResult,
    InventoryState,
    TopologyEventKind,
)
from pylontech_console.domain.info import ModuleIdentity
from pylontech_console.domain.pwr import PwrPosition, PwrSummary

UTC = timezone.utc
T1 = datetime(2026, 7, 17, 1, 0, tzinfo=UTC)
T2 = datetime(2026, 7, 17, 2, 0, tzinfo=UTC)


def power(position: int, *, present: bool = True) -> PwrPosition:
    value = 50000 if present else None
    return PwrPosition(
        position=position,
        present=present,
        voltage_mv=value,
        current_ma=-1000 if present else None,
        temperature_mc=25000 if present else None,
        lowest_temperature_mc=24000 if present else None,
        highest_temperature_mc=26000 if present else None,
        lowest_cell_voltage_mv=3300 if present else None,
        highest_cell_voltage_mv=3310 if present else None,
        base_status="Dischg" if present else "Absent",
        voltage_status="Normal" if present else None,
        current_status="Normal" if present else None,
        temperature_status="Normal" if present else None,
        soc_percent=80 if present else None,
        device_time=None,
        battery_voltage_status="Normal" if present else None,
        battery_temperature_status="Normal" if present else None,
        mosfet_temperature_mc=None,
        mosfet_temperature_status=None,
    )


def summary(
    *positions: PwrPosition,
    received_at: datetime = T1,
) -> PwrSummary:
    return PwrSummary(received_at=received_at, positions=positions)


def identity(
    position: int,
    barcode: str,
    *,
    received_at: datetime = T1,
) -> ModuleIdentity:
    return ModuleIdentity(
        received_at=received_at,
        position=position,
        barcode=barcode,
        manufacturer="Pylon",
        device_name="US2000C",
        board_version="V10R04",
        main_software_version="B67.5.0",
        software_version="V1.7",
        boot_version="V2.0",
        communication_version="V2.0",
        release_date_raw="20-12-11",
        specification="48V/50AH",
        cell_count=15,
        max_discharge_current_ma=-90000,
        max_charge_current_ma=90000,
        epon_port_rate=1200,
        console_port_rate=115200,
    )


class FakeReader:
    def __init__(
        self,
        responses: Mapping[int, ModuleIdentity | Exception],
    ) -> None:
        self.responses = responses
        self.calls: list[int] = []
        self.active_calls = 0
        self.maximum_active_calls = 0

    async def read_identity(self, position: int) -> ModuleIdentity:
        self.calls.append(position)
        self.active_calls += 1
        self.maximum_active_calls = max(
            self.maximum_active_calls,
            self.active_calls,
        )
        await asyncio.sleep(0)
        self.active_calls -= 1
        response = self.responses[position]
        if isinstance(response, Exception):
            raise response
        return response


async def run_cycle(
    pwr: PwrSummary,
    responses: Mapping[int, ModuleIdentity | Exception],
    previous: InventoryState | None = None,
) -> tuple[DiscoveryResult, FakeReader]:
    reader = FakeReader(responses)
    result = await discover_modules(
        pwr,
        InventoryState.empty() if previous is None else previous,
        reader,
    )
    return result, reader


@pytest.mark.asyncio
async def test_first_dynamic_discovery_is_barcode_keyed() -> None:
    result, reader = await run_cycle(
        summary(power(2), power(5), power(9, present=False)),
        {2: identity(2, "A"), 5: identity(5, "B")},
    )

    assert reader.calls == [2, 5]
    assert reader.maximum_active_calls == 1
    assert dict(result.state.positions) == {2: "A", 5: "B"}
    assert list(result.state.modules) == ["A", "B"]
    assert result.state.modules["A"].power == power(2)
    assert [event.kind for event in result.events] == [
        TopologyEventKind.MODULE_DISCOVERED,
        TopologyEventKind.MODULE_DISCOVERED,
    ]


@pytest.mark.asyncio
async def test_unchanged_topology_updates_last_seen_without_event() -> None:
    first, _ = await run_cycle(
        summary(power(1)),
        {1: identity(1, "A")},
    )
    second, _ = await run_cycle(
        summary(power(1), received_at=T2),
        {1: identity(1, "A", received_at=T2)},
        first.state,
    )

    record = second.state.modules["A"]
    assert record.first_seen_at == T1
    assert record.last_seen_at == T2
    assert second.events == ()


@pytest.mark.asyncio
async def test_adds_and_removes_modules_without_losing_history() -> None:
    first, _ = await run_cycle(
        summary(power(1), power(2)),
        {1: identity(1, "A"), 2: identity(2, "B")},
    )
    second, _ = await run_cycle(
        summary(power(2), power(3), received_at=T2),
        {2: identity(2, "B", received_at=T2), 3: identity(3, "C", received_at=T2)},
        first.state,
    )

    assert list(second.state.modules) == ["A", "B", "C"]
    assert second.state.modules["A"].present is False
    assert second.state.modules["A"].current_position is None
    assert second.state.modules["A"].power is None
    assert [event.kind for event in second.events] == [
        TopologyEventKind.MODULE_DISCOVERED,
        TopologyEventKind.MODULE_REMOVED,
    ]


@pytest.mark.asyncio
async def test_reappearing_module_preserves_first_seen() -> None:
    first, _ = await run_cycle(
        summary(power(1)),
        {1: identity(1, "A")},
    )
    removed, _ = await run_cycle(
        summary(received_at=T2),
        {},
        first.state,
    )
    t3 = T2 + timedelta(hours=1)
    returned, _ = await run_cycle(
        summary(power(4), received_at=t3),
        {4: identity(4, "A", received_at=t3)},
        removed.state,
    )

    record = returned.state.modules["A"]
    assert record.first_seen_at == T1
    assert record.current_position == 4
    assert [event.kind for event in returned.events] == [
        TopologyEventKind.MODULE_REAPPEARED,
    ]


@pytest.mark.asyncio
async def test_known_module_moves() -> None:
    first, _ = await run_cycle(
        summary(power(1)),
        {1: identity(1, "A")},
    )
    moved, _ = await run_cycle(
        summary(power(4), received_at=T2),
        {4: identity(4, "A", received_at=T2)},
        first.state,
    )

    assert moved.state.positions == {4: "A"}
    assert [event.kind for event in moved.events] == [
        TopologyEventKind.MODULE_MOVED,
    ]
    assert moved.events[0].previous_position == 1


@pytest.mark.asyncio
async def test_two_modules_exchange_positions_without_replacement() -> None:
    first, _ = await run_cycle(
        summary(power(1), power(2)),
        {1: identity(1, "A"), 2: identity(2, "B")},
    )
    exchanged, _ = await run_cycle(
        summary(power(1), power(2), received_at=T2),
        {1: identity(1, "B", received_at=T2), 2: identity(2, "A", received_at=T2)},
        first.state,
    )

    assert dict(exchanged.state.positions) == {1: "B", 2: "A"}
    assert [event.kind for event in exchanged.events] == [
        TopologyEventKind.MODULE_MOVED,
        TopologyEventKind.MODULE_MOVED,
    ]


@pytest.mark.asyncio
async def test_replacement_preserves_old_record() -> None:
    first, _ = await run_cycle(
        summary(power(1)),
        {1: identity(1, "A")},
    )
    replaced, _ = await run_cycle(
        summary(power(1), received_at=T2),
        {1: identity(1, "B", received_at=T2)},
        first.state,
    )

    assert set(replaced.state.modules) == {"A", "B"}
    assert replaced.state.modules["A"].present is False
    assert [event.kind for event in replaced.events] == [
        TopologyEventKind.MODULE_DISCOVERED,
        TopologyEventKind.MODULE_REPLACED_AT_POSITION,
    ]
    assert replaced.events[1].replaced_barcode == "A"


@pytest.mark.asyncio
async def test_duplicate_barcode_excludes_both_positions() -> None:
    result, _ = await run_cycle(
        summary(power(1), power(2)),
        {1: identity(1, "A"), 2: identity(2, "A")},
    )

    assert dict(result.state.positions) == {}
    assert dict(result.state.modules) == {}
    assert [error.kind for error in result.errors] == [
        DiscoveryErrorKind.DUPLICATE_BARCODE,
        DiscoveryErrorKind.DUPLICATE_BARCODE,
    ]
    assert [event.kind for event in result.events] == [
        TopologyEventKind.INVENTORY_ERROR,
        TopologyEventKind.INVENTORY_ERROR,
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "kind"),
    [
        (identity(1, "   "), DiscoveryErrorKind.MISSING_BARCODE),
        (identity(2, "A"), DiscoveryErrorKind.POSITION_MISMATCH),
        (RuntimeError("sensitive details"), DiscoveryErrorKind.IDENTITY_READ_FAILED),
    ],
)
async def test_invalid_identity_is_structured_error(
    response: ModuleIdentity | Exception,
    kind: DiscoveryErrorKind,
) -> None:
    result, _ = await run_cycle(
        summary(power(1)),
        {1: response},
    )

    assert result.errors[0].kind is kind
    assert "sensitive details" not in result.errors[0].detail
    assert dict(result.state.positions) == {}


@pytest.mark.asyncio
async def test_one_failure_does_not_discard_valid_module() -> None:
    result, _ = await run_cycle(
        summary(power(1), power(2)),
        {1: RuntimeError("failed"), 2: identity(2, "B")},
    )

    assert dict(result.state.positions) == {2: "B"}
    assert result.state.modules["B"].power == power(2)
    assert result.errors[0].position == 1


@pytest.mark.asyncio
async def test_unresolved_old_position_never_reuses_identity_or_measurement() -> None:
    first, _ = await run_cycle(
        summary(power(1)),
        {1: identity(1, "A")},
    )
    unresolved, _ = await run_cycle(
        summary(power(1), received_at=T2),
        {1: RuntimeError("failed")},
        first.state,
    )

    record = unresolved.state.modules["A"]
    assert record.present is None
    assert record.current_position is None
    assert record.power is None
    assert dict(unresolved.state.positions) == {}
    assert TopologyEventKind.MODULE_REMOVED not in {
        event.kind for event in unresolved.events
    }


@pytest.mark.asyncio
async def test_normalizes_timestamps_to_utc() -> None:
    offset = timezone(timedelta(hours=2))
    result, _ = await run_cycle(
        summary(power(1), received_at=datetime(2026, 7, 17, 3, 0, tzinfo=offset)),
        {
            1: identity(
                1,
                "A",
                received_at=datetime(2026, 7, 17, 3, 1, tzinfo=offset),
            ),
        },
    )

    assert result.state.observed_at == datetime(2026, 7, 17, 1, 0, tzinfo=UTC)
    assert result.state.modules["A"].last_seen_at == datetime(
        2026,
        7,
        17,
        1,
        1,
        tzinfo=UTC,
    )


@pytest.mark.asyncio
async def test_naive_identity_timestamp_is_position_error() -> None:
    result, _ = await run_cycle(
        summary(power(1), power(2)),
        {
            1: identity(1, "A", received_at=datetime(2026, 7, 17)),
            2: identity(2, "B"),
        },
    )

    assert result.errors[0].kind is DiscoveryErrorKind.INVALID_TIMESTAMP
    assert dict(result.state.positions) == {2: "B"}


@pytest.mark.asyncio
async def test_naive_summary_timestamp_is_input_error() -> None:
    with pytest.raises(DiscoveryInputError) as raised:
        await run_cycle(
            summary(power(1), received_at=datetime(2026, 7, 17)),
            {1: identity(1, "A")},
        )

    assert raised.value.kind is DiscoveryErrorKind.INVALID_TIMESTAMP


@pytest.mark.asyncio
async def test_duplicate_pwr_position_is_input_error() -> None:
    with pytest.raises(DiscoveryInputError) as raised:
        await run_cycle(
            summary(power(1), power(1)),
            {1: identity(1, "A")},
        )

    assert raised.value.kind is DiscoveryErrorKind.INCONSISTENT_INPUT


@pytest.mark.asyncio
async def test_results_are_read_only_and_previous_is_not_mutated() -> None:
    previous = InventoryState.empty()
    result, _ = await run_cycle(
        summary(power(1)),
        {1: identity(1, "A")},
        previous,
    )

    assert dict(previous.positions) == {}
    assert dict(previous.modules) == {}
    with pytest.raises(TypeError):
        result.state.positions[2] = "B"  # type: ignore[index]
    with pytest.raises(TypeError):
        result.state.modules["B"] = result.state.modules["A"]  # type: ignore[index]


@pytest.mark.asyncio
async def test_error_and_mapping_order_follow_pwr_response() -> None:
    result, _ = await run_cycle(
        summary(power(5), power(2), power(9)),
        {
            5: RuntimeError("failed"),
            2: identity(2, "B"),
            9: identity(8, "C"),
        },
    )

    assert list(result.state.positions) == [2]
    assert [error.position for error in result.errors] == [5, 9]
