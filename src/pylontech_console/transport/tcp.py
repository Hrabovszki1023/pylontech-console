import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

ResponseT = TypeVar("ResponseT")


class TransportNotConnectedError(RuntimeError):
    """Raised when an exchange is attempted without an open connection."""


class TransportResponseTimeoutError(TimeoutError):
    """Raised when a complete exchange exceeds its response timeout."""


class AsyncTcpTransport:
    """Own the asynchronous TCP connection lifecycle."""

    def __init__(
        self,
        host: str,
        port: int,
        connect_timeout_seconds: float,
    ) -> None:
        self._host = host
        self._port = port
        self._connect_timeout_seconds = connect_timeout_seconds
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._exchange_lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        """Return whether an open TCP writer is currently owned."""

        return self._writer is not None and not self._writer.is_closing()

    async def connect(self) -> None:
        """Open the configured TCP connection once."""

        if self.is_connected:
            return

        self._reader = None
        self._writer = None
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port),
            timeout=self._connect_timeout_seconds,
        )
        self._reader = reader
        self._writer = writer

    async def disconnect(self) -> None:
        """Close the owned TCP connection if one exists."""

        writer = self._writer
        self._reader = None
        self._writer = None

        if writer is None:
            return

        writer.close()
        await writer.wait_closed()

    async def exchange(
        self,
        request: bytes,
        read_response: Callable[[asyncio.StreamReader], Awaitable[ResponseT]],
        response_timeout_seconds: float,
    ) -> ResponseT:
        """Write bytes and return one response while serializing access."""

        async with self._exchange_lock:
            reader = self._reader
            writer = self._writer
            if (
                reader is None
                or writer is None
                or writer.is_closing()
            ):
                raise TransportNotConnectedError("TCP transport is not connected")

            async def run_exchange() -> ResponseT:
                writer.write(request)
                await writer.drain()
                return await read_response(reader)

            try:
                return await asyncio.wait_for(
                    run_exchange(),
                    timeout=response_timeout_seconds,
                )
            except TimeoutError as error:
                await self._disconnect_after_failure()
                raise TransportResponseTimeoutError(
                    "TCP response timeout expired",
                ) from error
            except Exception:
                await self._disconnect_after_failure()
                raise

    async def _disconnect_after_failure(self) -> None:
        try:
            await self.disconnect()
        except OSError:
            pass
