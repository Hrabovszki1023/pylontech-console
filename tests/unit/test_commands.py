from datetime import datetime, timezone
from pathlib import Path

import pytest

from pylontech_console.commands import ReadOnlyPylontechClient

CAPTURES = Path(__file__).parents[2] / "captures" / "US2000C" / "B67.5.0"
NOW = datetime(2026, 7, 19, 12, tzinfo=timezone.utc)


def payload(name: str) -> str:
    text = (CAPTURES / name).read_text(encoding="ascii")
    return text.split("@", maxsplit=1)[1].split("$$", maxsplit=1)[0].strip()


class FakeConsole:
    def __init__(self) -> None:
        self.commands: list[str] = []

    async def execute(self, command: str) -> str:
        self.commands.append(command)
        names = {
            "pwr": "pwr.txt",
            "pwrsys": "pwrsys.txt",
            "info 2": "info-2.txt",
            "pwr 2": "pwr-2.txt",
            "bat 2": "bat-2.txt",
        }
        return payload(names[command])


@pytest.mark.asyncio
async def test_typed_client_emits_only_documented_commands() -> None:
    console = FakeConsole()
    client = ReadOnlyPylontechClient(console, lambda: NOW)

    await client.read_topology()
    await client.read_rack()
    await client.read_identity(2)
    await client.read_module(2)
    await client.read_cells(2)

    assert console.commands == ["pwr", "pwrsys", "info 2", "pwr 2", "bat 2"]


@pytest.mark.asyncio
@pytest.mark.parametrize("position", [0, 17])
async def test_typed_client_rejects_invalid_position_without_command(
    position: int,
) -> None:
    console = FakeConsole()
    client = ReadOnlyPylontechClient(console, lambda: NOW)

    with pytest.raises(ValueError, match="outside"):
        await client.read_cells(position)

    assert console.commands == []
