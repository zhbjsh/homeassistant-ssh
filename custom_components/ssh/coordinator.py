from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from time import time
from typing import TYPE_CHECKING

from ssh_terminal_manager import (
    CommandError,
    CommandOutput,
    SensorCommand,
    SSHAuthenticationError,
    SSHHostKeyUnknownError,
    SSHManager,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from .entry_data import EntryData

FAST_UPDATE_INTERVAL = 2
FAST_UPDATE_MAXIMUM = 60


class BaseCoordinator(DataUpdateCoordinator):
    _remove_listener: Callable | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        manager: SSHManager,
        name: str,
        update_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            manager.logger,
            name=name,
            update_interval=update_interval,
        )
        self._manager = manager
        self.start()

    @property
    def _coordinators(self) -> list[BaseCoordinator]:
        entry = self.config_entry
        entry_data: EntryData = self.hass.data[entry.domain][entry.entry_id]
        return entry_data.coordinators

    def start(self):
        """Add listener to keep updating without entities."""
        if not self._listeners:
            self._remove_listener = self.async_add_listener(lambda: None)

    def stop(self):
        """Remove listener to stop updating."""
        if self._listeners:
            self._remove_listener()

    def stop_all(self) -> None:
        """Stop all coordinators."""
        for coordinator in self._coordinators:
            coordinator.stop()


class StateCoordinator(BaseCoordinator):
    _fast_update: tuple[float, Callable[[None], bool]] | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        manager: SSHManager,
        update_interval: int,
    ) -> None:
        super().__init__(
            hass,
            manager,
            f"{manager.name} state",
            timedelta(seconds=update_interval),
        )
        self._regular_update_interval = self.update_interval

    async def _async_update_data(self) -> None:
        try:
            await self._manager.async_update_state()
        except (SSHAuthenticationError, SSHHostKeyUnknownError) as exc:
            self.stop_all()
            raise ConfigEntryAuthFailed(exc) from exc
        except Exception as exc:
            raise UpdateFailed(f"Exception updating {self.name}: {exc}") from exc

        if self._fast_update is None:
            return

        start_time, complete = self._fast_update

        if complete() or time() - start_time > FAST_UPDATE_MAXIMUM:
            self._fast_update = None
            self.update_interval = self._regular_update_interval

    async def _async_start_fast_update(self, complete: Callable[[None], bool]) -> None:
        self._fast_update = time(), complete
        self.update_interval = timedelta(seconds=FAST_UPDATE_INTERVAL)
        await self.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn on.

        Start fast update until the device is up.
        """
        await self._async_start_fast_update(lambda: self._manager.is_up)
        await self._manager.async_turn_on()

    async def async_turn_off(self) -> CommandOutput:
        """Turn off.

        Start fast update until the device is down.
        """
        await self._async_start_fast_update(lambda: self._manager.is_down)
        return await self._manager.async_turn_off()

    async def async_restart(self) -> CommandOutput:
        """Restart.

        Start fast update until the device is down.
        """
        await self._async_start_fast_update(lambda: self._manager.is_down)
        return await self._manager.async_restart()


class SensorCommandCoordinator(BaseCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        manager: SSHManager,
        command: SensorCommand,
    ) -> None:
        super().__init__(
            hass,
            manager,
            f"{manager.name} {', '.join(sensor.key for sensor in command.sensors)}",
            timedelta(seconds=command.interval) if command.interval else None,
        )
        self._command = command

    async def _async_update_data(self) -> None:
        if not self._manager.is_up:
            return
        try:
            await self._manager.async_execute_command(self._command)
        except CommandError as exc:
            cause = exc.__cause__
            if isinstance(cause, (SSHAuthenticationError, SSHHostKeyUnknownError)):
                self.stop_all()
                raise ConfigEntryAuthFailed(exc) from exc
        except (SSHAuthenticationError, SSHHostKeyUnknownError) as exc:
            self.stop_all()
            raise ConfigEntryAuthFailed(exc) from exc
        except Exception as exc:
            raise UpdateFailed(f"Exception updating {self.name}: {exc}") from exc
