import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar, cast

import serial_asyncio

from pylontech_console.transport.tcp import (
    RECONNECT_MAX_SECONDS,
    RECONNECT_MIN_SECONDS,
    TransportNotConnectedError,
    TransportResponseTimeoutError,
)

ResponseT = TypeVar("ResponseT")
LOGGER = logging.getLogger(__name__)

SerialOpener = Callable[..., Awaitable[tuple[asyncio.StreamReader, asyncio.StreamWriter]]]


class AsyncSerialTransport:
    """Own an asynchronous local USB/serial connection lifecycle."""

    def __init__(
        self,
        device: str,
        baudrate: int,
        connect_timeout_seconds: float,
        *,
        reconnect_min_seconds: float = RECONNECT_MIN_SECONDS,
        reconnect_max_seconds: float = RECONNECT_MAX_SECONDS,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        opener: SerialOpener | None = None,
    ) -> None:
        if reconnect_min_seconds <= 0:
            raise ValueError("reconnect minimum must be greater than zero")
        if reconnect_max_seconds < reconnect_min_seconds:
            raise ValueError("reconnect maximum must not be below minimum")
        self._device = device
        self._baudrate = baudrate
        self._connect_timeout_seconds = connect_timeout_seconds
        self._reconnect_min_seconds = reconnect_min_seconds
        self._reconnect_max_seconds = reconnect_max_seconds
        self._sleep = sleep
        self._opener = opener or cast(SerialOpener, serial_asyncio.open_serial_connection)
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._exchange_lock = asyncio.Lock()
        self._connect_lock = asyncio.Lock()
        self._reconnect_required = False
        self._recovery_in_progress = False
        self._reconnect_delay_seconds = reconnect_min_seconds
        self._connection_generation = 0

    @property
    def is_connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    @property
    def connection_generation(self) -> int:
        return self._connection_generation

    async def connect(self) -> None:
        async with self._connect_lock:
            if self.is_connected:
                return
            self._reader = None
            self._writer = None
            reader, writer = await asyncio.wait_for(
                self._opener(
                    url=self._device,
                    baudrate=self._baudrate,
                    bytesize=8,
                    parity="N",
                    stopbits=1,
                    xonxoff=False,
                    rtscts=False,
                    dsrdtr=False,
                ),
                timeout=self._connect_timeout_seconds,
            )
            self._reader = reader
            self._writer = writer
            self._connection_generation += 1
            self._reconnect_required = False

    async def ensure_connected(self) -> None:
        if self.is_connected and not self._reconnect_required:
            return
        if self._reconnect_required:
            await self._reconnect()
        else:
            await self.connect()

    async def disconnect(self) -> None:
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
        async with self._exchange_lock:
            if self._reconnect_required:
                await self._reconnect()
            reader = self._reader
            writer = self._writer
            if reader is None or writer is None or writer.is_closing():
                raise TransportNotConnectedError("serial transport is not connected")

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
                    "serial response timeout expired",
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
        LOGGER.warning("serial reconnect scheduled in %.1f seconds", delay)
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
                "serial reconnect failed; next attempt in %.1f seconds",
                self._reconnect_delay_seconds,
                exc_info=True,
            )
            raise
        LOGGER.warning("serial reconnect succeeded")
