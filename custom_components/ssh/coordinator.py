from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from ssh_terminal_manager import (
    CommandOutput,
    ExecutionError,
    SensorCommand,
    SSHAuthenticationError,
    SSHHostKeyUnknownError,
    SSHManager,
)

from homeassistant.core import HomeAssistant, HomeAssistantError, ServiceValidationError
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from .entry_data import EntryData

FAST_UPDATE_INTERVAL = timedelta(seconds=1)


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
    def _entry_data(self) -> EntryData:
        entry = self.config_entry
        return self.hass.data[entry.domain][entry.entry_id]

    async def _async_handle_auth_error(self, exc) -> None:
        if isinstance(exc, (SSHHostKeyUnknownError, SSHAuthenticationError)):
            await self._entry_data.async_shutdown()
            raise ConfigEntryAuthFailed(exc) from exc

    def start(self):
        """Add listener to keep updating without entities."""
        if not self._remove_listener:
            self._remove_listener = self.async_add_listener(lambda: None)

    def stop(self):
        """Remove listener to stop updating."""
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None

    async def async_shutdown(self):
        """Stop and shutdown."""
        self.stop()
        return await super().async_shutdown()


class StateCoordinator(BaseCoordinator):
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
            await self._manager.async_update(once=True, test=True)
        except Exception as exc:
            await self._async_handle_auth_error(exc)
            raise UpdateFailed(f"Exception updating {self.name}: {exc}") from exc

        if self._manager.state.request:
            self.update_interval = FAST_UPDATE_INTERVAL
        else:
            self.update_interval = self._regular_update_interval

    async def async_turn_on(self) -> None:
        """Turn on."""
        try:
            await self._manager.async_turn_on()
        except ValueError as exc:
            raise ServiceValidationError(exc) from exc
        await self.async_request_refresh()

    async def async_turn_off(self) -> CommandOutput:
        """Turn off."""
        try:
            output = await self._manager.async_turn_off()
        except (PermissionError, KeyError) as exc:
            raise ServiceValidationError(exc) from exc
        except ExecutionError as exc:
            raise HomeAssistantError(exc) from exc
        await self.async_request_refresh()
        return output

    async def async_restart(self) -> CommandOutput:
        """Restart."""
        try:
            output = await self._manager.async_restart()
        except KeyError as exc:
            raise ServiceValidationError(exc) from exc
        except ExecutionError as exc:
            raise HomeAssistantError(exc) from exc
        await self.async_request_refresh()
        return output

    async def async_set_sensor_value(self, key: str, value: Any) -> None:
        """Set sensor value."""
        try:
            await self._manager.async_set_sensor_value(key, value, raise_errors=True)
        except (KeyError, TypeError, ValueError) as exc:
            raise ServiceValidationError(exc) from exc
        except ExecutionError as exc:
            raise HomeAssistantError(exc) from exc


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
        except ExecutionError as exc:
            await self._async_handle_auth_error(exc.__cause__)
        except Exception as exc:
            raise UpdateFailed(f"Exception updating {self.name}: {exc}") from exc
