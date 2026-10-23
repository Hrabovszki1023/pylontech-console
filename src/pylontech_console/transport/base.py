import asyncio
from collections.abc import Awaitable, Callable
from typing import Protocol, TypeVar

ResponseT = TypeVar("ResponseT")


class AsyncTransport(Protocol):
    """Transport-independent lifecycle required by the console client."""

    @property
    def is_connected(self) -> bool: ...

    @property
    def connection_generation(self) -> int: ...

    async def connect(self) -> None: ...

    async def ensure_connected(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def exchange(
        self,
        request: bytes,
        read_response: Callable[[asyncio.StreamReader], Awaitable[ResponseT]],
        response_timeout_seconds: float,
    ) -> ResponseT: ...
