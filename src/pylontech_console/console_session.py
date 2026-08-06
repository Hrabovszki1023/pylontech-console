import asyncio
import logging
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from threading import Lock
from typing import Protocol

from pylontech_console.framing.console import (
    ConsoleExchange,
    FramedConsoleClient,
)
from pylontech_console.transport.tcp import AsyncTcpTransport

SUCCESS_CONFIRMATION = "Command completed successfully"
USER_MODE_PWRSYS_REJECTION = "Unknown command 'pwrsys' - try 'help'"
LOGGER = logging.getLogger(__name__)


class ConsoleSessionMode(str, Enum):
    USER = "user"
    DEBUG = "debug"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ConsoleSessionHealth:
    mode: ConsoleSessionMode = ConsoleSessionMode.UNKNOWN
    authenticated: bool = False
    last_authenticated_at: datetime | None = None
    error: str | None = None


class ConsoleSessionHealthStore:
    def __init__(self, initial: ConsoleSessionHealth | None = None) -> None:
        self._value = initial or ConsoleSessionHealth()
        self._lock = Lock()

    def get(self) -> ConsoleSessionHealth:
        with self._lock:
            return self._value

    def set(self, value: ConsoleSessionHealth) -> None:
        with self._lock:
            self._value = value


class SessionClock(Protocol):
    def __call__(self) -> datetime: ...


def utc_now() -> datetime:
    return datetime.now(UTC)


class ConsoleAuthenticationError(RuntimeError):
    """Raised when an authenticated debug session cannot be established."""


class AuthenticatedConsoleClient:
    """Gate the read-only acquisition allowlist behind debug authentication."""

    def __init__(
        self,
        transport: AsyncTcpTransport,
        console: FramedConsoleClient,
        password: str,
        health: ConsoleSessionHealthStore,
        *,
        clock: SessionClock = utc_now,
    ) -> None:
        self._transport = transport
        self._console = console
        self._password = password
        self._health = health
        self._clock = clock
        self._verified_generation: int | None = None
        self._lock = asyncio.Lock()

    async def establish(self) -> None:
        async with self._lock:
            await self._establish_locked()

    async def execute(self, command: str) -> str:
        async with self._lock:
            await self._transport.ensure_connected()
            if self._verified_generation != self._transport.connection_generation:
                await self._establish_locked()
            try:
                exchange = await self._console.exchange(command)
            except Exception:
                self._mark_unverified("console exchange failed")
                raise
            if exchange.mode is not ConsoleSessionMode.DEBUG:
                self._health.set(
                    ConsoleSessionHealth(
                        mode=exchange.mode,
                        authenticated=False,
                        error="console session left debug mode",
                    ),
                )
                self._verified_generation = None
                raise ConsoleAuthenticationError(
                    "console session left debug mode",
                )
            return exchange.payload

    async def logout(self) -> None:
        async with self._lock:
            health = self._health.get()
            if (
                not self._transport.is_connected
                or not health.authenticated
                or health.mode is not ConsoleSessionMode.DEBUG
            ):
                return
            try:
                exchange = await self._console.exchange("logout")
                if not (
                    exchange.succeeded
                    and exchange.mode is ConsoleSessionMode.USER
                ):
                    raise ConsoleAuthenticationError(
                        "console logout was not confirmed",
                    )
                self._health.set(
                    ConsoleSessionHealth(mode=ConsoleSessionMode.USER),
                )
                self._verified_generation = None
            except Exception:
                self._mark_unverified("console logout failed")
                LOGGER.warning("console logout failed")

    async def _establish_locked(self) -> None:
        try:
            await self._transport.ensure_connected()
            probe = await self._console.exchange("pwrsys")
            if probe.succeeded and probe.mode is ConsoleSessionMode.DEBUG:
                self._mark_authenticated()
                return
            if not self._is_confirmed_user_mode(probe):
                raise ConsoleAuthenticationError(
                    "console mode could not be determined",
                )
            login = await self._console.exchange(f"login {self._password}")
            if not (
                login.succeeded
                and login.mode is ConsoleSessionMode.DEBUG
            ):
                mode = login.mode
                self._health.set(
                    ConsoleSessionHealth(
                        mode=mode,
                        authenticated=False,
                        error="console authentication failed",
                    ),
                )
                self._verified_generation = None
                raise ConsoleAuthenticationError(
                    "console authentication failed",
                )
            self._mark_authenticated()
        except ConsoleAuthenticationError:
            if self._health.get().error is None:
                self._mark_unverified("console authentication failed")
            raise
        except Exception:
            if self._health.get().error is None:
                self._mark_unverified("console session establishment failed")
            raise

    @staticmethod
    def _is_confirmed_user_mode(exchange: ConsoleExchange) -> bool:
        lines = tuple(
            line.strip()
            for line in exchange.payload.splitlines()
            if line.strip()
        )
        return (
            exchange.mode is ConsoleSessionMode.USER
            and USER_MODE_PWRSYS_REJECTION in lines
        )

    def _mark_authenticated(self) -> None:
        self._health.set(
            ConsoleSessionHealth(
                mode=ConsoleSessionMode.DEBUG,
                authenticated=True,
                last_authenticated_at=self._clock().astimezone(UTC),
            ),
        )
        self._verified_generation = self._transport.connection_generation

    def _mark_unverified(self, error: str) -> None:
        previous = self._health.get()
        self._health.set(
            replace(
                previous,
                mode=ConsoleSessionMode.UNKNOWN,
                authenticated=False,
                error=error,
            ),
        )
        self._verified_generation = None
