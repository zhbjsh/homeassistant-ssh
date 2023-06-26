from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import timedelta
from functools import wraps
import logging

from ssh_remote_control import (
    Command,
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

from .helpers import get_command_renderer

_LOGGER = logging.getLogger(__name__)


def log_errors(coro: Coroutine):
    """Log errors decorator."""

    @wraps(coro)
    async def wrapper(coordinator: DataUpdateCoordinator, *args, **kwargs):
        try:
            return await coro(coordinator, *args, **kwargs)
        except Exception as exc:  # pylint: disable=broad-except
            coordinator.logger.warning(
                "%s: %s failed, %s", coordinator.name, coro.__name__, exc
            )

    return wrapper


class StateCoordinator(DataUpdateCoordinator):
    """The StateCoordinator class."""

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

    @log_errors
    async def async_execute_command(
        self,
        command_string: str,
        timeout: int | None = None,
        context: dict | None = None,
    ) -> None:
        """Execute a command.

        Fires 'ssh_command_executed' event after execution.
        """
        command = Command(
            command_string,
            timeout=timeout,
            renderer=get_command_renderer(self.hass),
        )

        output = await self.remote.async_execute_command(command, context)

        self.hass.bus.fire(
            "ssh_command_executed",
            {
                "command": command_string,
                "output": {
                    "stdout": output.stdout,
                    "stderr": output.stderr,
                    "code": output.code,
                },
            },
        )

    @log_errors
    async def async_run_action(
        self, action_key: str, context: dict | None = None
    ) -> None:
        """Run an action."""
        await self.remote.async_run_action(action_key, context)

    @log_errors
    async def async_poll_sensors(self, sensor_keys: list[str]) -> None:
        """Poll sensors."""
        await self.remote.async_poll_sensors(sensor_keys)

    @log_errors
    async def async_set_sensor_value(self, sensor_key: str, value: bool) -> None:
        """Set the value of a sensor."""
        await self.remote.async_set_sensor_value(sensor_key, value)

    @log_errors
    async def async_turn_on(self) -> None:
        """Turn on."""
        await self.remote.turn_on()

    @log_errors
    async def async_turn_off(self) -> None:
        """Turn off."""
        await self.remote.turn_off()


class SensorCommandCoordinator(DataUpdateCoordinator):
    """The SensorCommandCoordinator class."""

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
        self.command = command
        self.stop: Callable = self.async_add_listener(lambda: None)

    async def _async_update_data(self) -> None:
        if not self.remote.state.is_connected:
            return
        try:
            await self.remote.async_execute_command(self.command)
        except (CommandFormatError, CommandExecuteError):
            pass
        except Exception as exc:
            raise UpdateFailed(f"Exception updating {self.name}: {exc}") from exc
