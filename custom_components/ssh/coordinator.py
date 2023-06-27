from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging

from ssh_remote_control import (
    CommandExecuteError,
    CommandFormatError,
    Remote,
    SensorCommand,
    SSHAuthError,
    SSHHostKeyUnknownError,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class StateCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        remote: Remote,
        update_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=remote.name,
            update_interval=timedelta(seconds=update_interval),
        )
        self.remote = remote
        # Add listener to keep updating without any entities
        self.stop: Callable = self.async_add_listener(lambda: None)

    async def _async_update_data(self) -> None:
        try:
            await self.remote.async_update_state()
        except SSHHostKeyUnknownError as exc:
            self.stop()
            raise ConfigEntryError from exc
        except SSHAuthError as exc:
            self.stop()
            raise ConfigEntryAuthFailed from exc
        except Exception as exc:
            raise UpdateFailed(f"Exception during update: {exc}") from exc


class SensorCommandCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        remote: Remote,
        command: SensorCommand,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{remote.name} "
            + f"(sensor command {remote.sensor_commands.index(command)})",
            update_interval=timedelta(seconds=command.interval),
        )
        self.remote = remote
        self._command = command
        # Add listener to keep updating without any entities
        self.stop: Callable = self.async_add_listener(lambda: None)

    async def _async_update_data(self) -> None:
        if not self.remote.state.is_connected:
            return
        try:
            await self.remote.async_execute_command(self._command)
        except (CommandFormatError, CommandExecuteError):
            pass
        except Exception as exc:
            raise UpdateFailed(f"Exception updating {self.name}: {exc}") from exc
