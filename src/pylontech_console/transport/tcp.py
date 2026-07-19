import asyncio


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
