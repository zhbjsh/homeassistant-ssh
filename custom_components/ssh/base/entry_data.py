from dataclasses import dataclass

from ssh_terminal_manager import ActionKey, SensorKey, SSHManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntry

from .coordinator import SensorCommandCoordinator, StateCoordinator


@dataclass
class EntryData:
    config_entry: ConfigEntry
    device_entry: DeviceEntry
    manager: SSHManager
    state_coordinator: StateCoordinator
    command_coordinators: list[SensorCommandCoordinator]
    ignored_action_keys: list[ActionKey] | None = None
    ignored_sensor_keys: list[SensorKey] | None = None
