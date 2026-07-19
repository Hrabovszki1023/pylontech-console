import asyncio

from pylontech_console.transport.tcp import AsyncTcpTransport

COMMAND_TERMINATOR = b"\r"
RESPONSE_START_MARKER = b"@"
RESPONSE_END_MARKER = b"$$"
MAX_EXCHANGE_BYTES = 16_384
READ_CHUNK_BYTES = 4_096


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


async def read_framed_ascii_payload(
    reader: asyncio.StreamReader,
    max_exchange_bytes: int = MAX_EXCHANGE_BYTES,
) -> str:
    """Read and validate one complete ASCII payload."""

    exchange = bytearray()

    while True:
        chunk = await reader.read(READ_CHUNK_BYTES)
        if not chunk:
            raise IncompleteResponseError(
                "TCP connection closed before the response end marker",
            )

        exchange.extend(chunk)
        start_index = exchange.find(RESPONSE_START_MARKER)
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

                framed_exchange = bytes(exchange[:exchange_end])
                try:
                    framed_exchange.decode("ascii")
                except UnicodeDecodeError as error:
                    raise ResponseEncodingError(
                        "console response must contain only ASCII",
                    ) from error

                payload = bytes(
                    exchange[
                        start_index + len(RESPONSE_START_MARKER) : end_index
                    ],
                )
                payload = _remove_leading_line_ending(payload)
                payload = _remove_trailing_line_ending(payload)
                return payload.decode("ascii")

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

        request = encode_command(command)
        return await self._transport.exchange(
            request,
            read_framed_ascii_payload,
            self._response_timeout_seconds,
        )
