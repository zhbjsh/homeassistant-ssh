from dataclasses import dataclass

from ssh_terminal_manager import ActionKey, SensorKey, SSHManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.device_registry import DeviceEntry

from .coordinator import BaseCoordinator, SensorCommandCoordinator, StateCoordinator


@dataclass
class EntryData:
    config_entry: ConfigEntry
    manager: SSHManager
    state_coordinator: StateCoordinator
    command_coordinators: list[SensorCommandCoordinator]
    platforms: list[Platform]
    ignored_action_keys: list[ActionKey] | None = None
    ignored_sensor_keys: list[SensorKey] | None = None
    device_entry: DeviceEntry | None = None

    @property
    def coordinators(self) -> list[BaseCoordinator]:
        """All coordinators of the config entry."""
        return [self.state_coordinator, *self.command_coordinators]

    async def async_shutdown(self) -> None:
        """Shutdown all coordinators and reset manager."""
        for coordinator in self.coordinators:
            await coordinator.async_shutdown()

        await self.manager.async_reset()
