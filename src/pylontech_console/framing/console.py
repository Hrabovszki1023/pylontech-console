import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pylontech_console.transport.tcp import AsyncTcpTransport

if TYPE_CHECKING:
    from pylontech_console.console_session import ConsoleSessionMode

COMMAND_TERMINATOR = b"\r"
RESPONSE_START_MARKER = b"@"
RESPONSE_END_MARKER = b"$$"
MAX_EXCHANGE_BYTES = 16_384
READ_CHUNK_BYTES = 4_096
USER_PROMPT = "pylon>"
DEBUG_PROMPT = "pylon_debug>"
SUCCESS_CONFIRMATION = "Command completed successfully"


class ConsoleProtocolError(RuntimeError):
    """Base class for console command and response protocol failures."""


class CommandEncodingError(ConsoleProtocolError):
    """Raised when a command cannot be represented as strict ASCII."""


class ResponseEncodingError(ConsoleProtocolError):
    """Raised when a response contains non-ASCII bytes."""


class IncompleteResponseError(ConsoleProtocolError):
    """Raised when the peer closes before a complete response arrives."""


class ResponseTooLargeError(ConsoleProtocolError):
    """Raised when a command exchange exceeds its byte limit."""


@dataclass(frozen=True)
class ConsoleExchange:
    payload: str
    prompt: str
    mode: "ConsoleSessionMode"
    succeeded: bool


def encode_command(command: str) -> bytes:
    """Encode one console command with the verified terminator."""

    try:
        return command.encode("ascii") + COMMAND_TERMINATOR
    except UnicodeEncodeError as error:
        raise CommandEncodingError("console command must contain only ASCII") from error


def _remove_leading_line_ending(payload: bytes) -> bytes:
    if payload.startswith(b"\r\n"):
        return payload[2:]
    if payload.startswith((b"\r", b"\n")):
        return payload[1:]
    return payload


def _remove_trailing_line_ending(payload: bytes) -> bytes:
    if payload.endswith(b"\r\n"):
        return payload[:-2]
    if payload.endswith((b"\r", b"\n")):
        return payload[:-1]
    return payload


def _find_response_start(exchange: bytearray) -> int:
    search_from = 0
    while True:
        index = exchange.find(RESPONSE_START_MARKER, search_from)
        if index < 0:
            return -1
        before_is_boundary = index == 0 or exchange[index - 1] in b"\r\n"
        after = index + len(RESPONSE_START_MARKER)
        after_is_boundary = (
            index == 0
            or after == len(exchange)
            or exchange[after] in b"\r\n"
        )
        if before_is_boundary and after_is_boundary:
            return index
        search_from = index + 1


async def read_console_exchange(
    reader: asyncio.StreamReader,
    max_exchange_bytes: int = MAX_EXCHANGE_BYTES,
) -> ConsoleExchange:
    """Read one framed ASCII payload and its following exact prompt."""

    exchange = bytearray()
    end_index: int | None = None

    while True:
        chunk = await reader.read(READ_CHUNK_BYTES)
        if not chunk:
            raise IncompleteResponseError(
                "TCP connection closed before the response end marker",
            )

        exchange.extend(chunk)
        start_index = _find_response_start(exchange)
        if start_index >= 0 and end_index is None:
            found_end = exchange.find(
                RESPONSE_END_MARKER,
                start_index + len(RESPONSE_START_MARKER),
            )
            if found_end >= 0:
                end_index = found_end
                exchange_end = end_index + len(RESPONSE_END_MARKER)
                if exchange_end > max_exchange_bytes:
                    raise ResponseTooLargeError(
                        f"console exchange exceeds {max_exchange_bytes} bytes",
                    )
                try:
                    bytes(exchange[:exchange_end]).decode("ascii")
                except UnicodeDecodeError as error:
                    raise ResponseEncodingError(
                        "console response must contain only ASCII",
                    ) from error

        if start_index >= 0 and end_index is not None:
            prompt_start = end_index + len(RESPONSE_END_MARKER)
            trailing = bytes(exchange[prompt_start:]).strip(b"\r\n")
            prompt: str | None = None
            if trailing == DEBUG_PROMPT.encode("ascii"):
                prompt = DEBUG_PROMPT
            elif trailing == USER_PROMPT.encode("ascii"):
                prompt = USER_PROMPT
            if prompt is not None:
                try:
                    bytes(exchange).decode("ascii")
                except UnicodeDecodeError as error:
                    raise ResponseEncodingError(
                        "console response must contain only ASCII",
                    ) from error
                payload_bytes = bytes(
                    exchange[
                        start_index + len(RESPONSE_START_MARKER) : end_index
                    ],
                )
                payload_bytes = _remove_leading_line_ending(payload_bytes)
                payload_bytes = _remove_trailing_line_ending(payload_bytes)
                payload = payload_bytes.decode("ascii")
                from pylontech_console.console_session import (  # noqa: PLC0415
                    ConsoleSessionMode,
                )

                mode = (
                    ConsoleSessionMode.DEBUG
                    if prompt == DEBUG_PROMPT
                    else ConsoleSessionMode.USER
                )
                return ConsoleExchange(
                    payload=payload,
                    prompt=prompt,
                    mode=mode,
                    succeeded=(
                        next(
                            (
                                line.strip()
                                for line in reversed(payload.splitlines())
                                if line.strip()
                            ),
                            None,
                        )
                        == SUCCESS_CONFIRMATION
                    ),
                )

        if len(exchange) > max_exchange_bytes:
            raise ResponseTooLargeError(
                f"console exchange exceeds {max_exchange_bytes} bytes",
            )


async def read_framed_ascii_payload(
    reader: asyncio.StreamReader,
    max_exchange_bytes: int = MAX_EXCHANGE_BYTES,
) -> str:
    """Backward-compatible payload-only reader used by parser unit tests."""

    exchange = bytearray()
    while True:
        chunk = await reader.read(READ_CHUNK_BYTES)
        if not chunk:
            raise IncompleteResponseError(
                "TCP connection closed before the response end marker",
            )
        exchange.extend(chunk)
        start_index = _find_response_start(exchange)
        if start_index >= 0:
            end_index = exchange.find(
                RESPONSE_END_MARKER,
                start_index + len(RESPONSE_START_MARKER),
            )
            if end_index >= 0:
                exchange_end = end_index + len(RESPONSE_END_MARKER)
                if exchange_end > max_exchange_bytes:
                    raise ResponseTooLargeError(
                        f"console exchange exceeds {max_exchange_bytes} bytes",
                    )
                try:
                    bytes(exchange[:exchange_end]).decode("ascii")
                except UnicodeDecodeError as error:
                    raise ResponseEncodingError(
                        "console response must contain only ASCII",
                    ) from error
                payload = bytes(exchange[start_index + 1 : end_index])
                return _remove_trailing_line_ending(
                    _remove_leading_line_ending(payload),
                ).decode("ascii")
        if len(exchange) > max_exchange_bytes:
            raise ResponseTooLargeError(
                f"console exchange exceeds {max_exchange_bytes} bytes",
            )


class FramedConsoleClient:
    """Execute one framed console exchange over an owned TCP transport."""

    def __init__(
        self,
        transport: AsyncTcpTransport,
        response_timeout_seconds: float,
    ) -> None:
        self._transport = transport
        self._response_timeout_seconds = response_timeout_seconds

    async def execute(self, command: str) -> str:
        """Send one command and return only its framed payload."""

        return (await self.exchange(command)).payload

    async def exchange(self, command: str) -> ConsoleExchange:
        """Send one command and return its payload and following prompt."""

        request = encode_command(command)
        return await self._transport.exchange(
            request,
            read_console_exchange,
            self._response_timeout_seconds,
        )
