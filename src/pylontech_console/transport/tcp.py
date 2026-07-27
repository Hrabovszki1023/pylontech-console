import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

ResponseT = TypeVar("ResponseT")
LOGGER = logging.getLogger(__name__)

RECONNECT_MIN_SECONDS = 1.0
RECONNECT_MAX_SECONDS = 30.0


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
        *,
        reconnect_min_seconds: float = RECONNECT_MIN_SECONDS,
        reconnect_max_seconds: float = RECONNECT_MAX_SECONDS,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if reconnect_min_seconds <= 0:
            raise ValueError("reconnect minimum must be greater than zero")
        if reconnect_max_seconds < reconnect_min_seconds:
            raise ValueError(
                "reconnect maximum must not be below minimum",
            )
        self._host = host
        self._port = port
        self._connect_timeout_seconds = connect_timeout_seconds
        self._reconnect_min_seconds = reconnect_min_seconds
        self._reconnect_max_seconds = reconnect_max_seconds
        self._sleep = sleep
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._exchange_lock = asyncio.Lock()
        self._reconnect_required = False
        self._recovery_in_progress = False
        self._reconnect_delay_seconds = self._reconnect_min_seconds

    @property
    def is_connected(self) -> bool:
        """Return whether an open TCP writer is currently owned."""

        return self._writer is not None and not self._writer.is_closing()

    async def connect(self) -> None:
        """Open the configured TCP connection once."""

        if self.is_connected:
            return

        reconnecting = self._reconnect_required
        self._reader = None
        self._writer = None
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port),
            timeout=self._connect_timeout_seconds,
        )
        self._reader = reader
        self._writer = writer
        self._reconnect_required = False
        if not reconnecting:
            self._recovery_in_progress = False
            self._reconnect_delay_seconds = self._reconnect_min_seconds

    async def disconnect(self) -> None:
        """Close the owned TCP connection if one exists."""

        self._reconnect_required = False
        self._recovery_in_progress = False
        self._reconnect_delay_seconds = self._reconnect_min_seconds
        await self._close_connection()

    async def _close_connection(self) -> None:
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
            if self._reconnect_required:
                await self._reconnect()

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
                result = await asyncio.wait_for(
                    run_exchange(),
                    timeout=response_timeout_seconds,
                )
                self._recovery_in_progress = False
                self._reconnect_delay_seconds = self._reconnect_min_seconds
                return result
            except TimeoutError as error:
                await self._disconnect_after_failure()
                raise TransportResponseTimeoutError(
                    "TCP response timeout expired",
                ) from error
            except Exception:
                await self._disconnect_after_failure()
                raise

    async def _disconnect_after_failure(self) -> None:
        if self._recovery_in_progress:
            self._reconnect_delay_seconds = min(
                self._reconnect_delay_seconds * 2,
                self._reconnect_max_seconds,
            )
        else:
            self._recovery_in_progress = True
            self._reconnect_delay_seconds = self._reconnect_min_seconds
        try:
            await self._close_connection()
        except OSError:
            pass
        finally:
            self._reconnect_required = True

    async def _reconnect(self) -> None:
        delay = self._reconnect_delay_seconds
        LOGGER.info(
            "Waveshare TCP reconnect scheduled in %.1f seconds",
            delay,
        )
        await self._sleep(delay)
        try:
            await self.connect()
        except (OSError, RuntimeError, TimeoutError):
            self._reconnect_required = True
            self._reconnect_delay_seconds = min(
                delay * 2,
                self._reconnect_max_seconds,
            )
            LOGGER.warning(
                "Waveshare TCP reconnect failed; "
                "next attempt in %.1f seconds",
                self._reconnect_delay_seconds,
                exc_info=True,
            )
            raise
        LOGGER.info("Waveshare TCP reconnect succeeded")
