from typing import Any

from ssh_remote_control import Sensor, ServiceCommand, State

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_CLASS, CONF_ENABLED, CONF_ICON
from homeassistant.helpers.entity import DeviceInfo, generate_entity_id
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import StateCoordinator


class BaseEntity(CoordinatorEntity):
    coordinator: StateCoordinator
    _entity_id_format: str
    _attr_has_entity_name = True

    def __init__(
        self,
        state_coordinator: StateCoordinator,
        config_entry: ConfigEntry,
        options: dict | None = None,
    ) -> None:
        super().__init__(state_coordinator)
        self._remote = state_coordinator.remote
        self._config_entry = config_entry
        self._options = options or {}
        self.entity_id = generate_entity_id(
            self._entity_id_format,
            f"{self.coordinator.name}_{self._id}",
            [],
            self.coordinator.hass,
        )

    @property
    def _id(self) -> str:
        return self.name

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.unique_id)},
            name=self._config_entry.title,
            sw_version=self._remote.os_version,
            hw_version=self._remote.machine_type,
        )

    @property
    def unique_id(self) -> str:
        return f"{self._config_entry.unique_id}_{self.entity_id}"

    @property
    def device_class(self) -> Any | None:
        return self._options.get(CONF_DEVICE_CLASS)

    @property
    def icon(self) -> str | None:
        return self._options.get(CONF_ICON)

    @property
    def entity_registry_enabled_default(self) -> bool:
        return self._options.get(CONF_ENABLED, True)

    def _handle_remote_state_change(self, state: State) -> None:
        self.schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        self._remote.state.on_change.subscribe(self._handle_remote_state_change)

    async def async_will_remove_from_hass(self) -> None:
        self._remote.state.on_change.unsubscribe(self._handle_remote_state_change)


class BaseServiceEntity(BaseEntity):
    def __init__(
        self,
        state_coordinator: StateCoordinator,
        config_entry: ConfigEntry,
        command: ServiceCommand,
    ) -> None:
        self._command = command
        super().__init__(state_coordinator, config_entry, command.options)

    @property
    def _id(self) -> str:
        return self.key

    @property
    def key(self) -> str:
        return self._command.key

    @property
    def name(self) -> str | None:
        return self._command.name

    @property
    def available(self) -> bool:
        return self._remote.state.is_connected


class BaseSensorEntity(BaseEntity):
    def __init__(
        self,
        state_coordinator: StateCoordinator,
        config_entry: ConfigEntry,
        sensor: Sensor,
    ) -> None:
        self._sensor = sensor
        super().__init__(state_coordinator, config_entry, sensor.options)

    @property
    def _id(self) -> str:
        return self.key

    @property
    def key(self) -> str:
        return self._sensor.key

    @property
    def name(self) -> str | None:
        return self._sensor.name

    @property
    def available(self) -> bool:
        return self._remote.state.is_connected

    def _handle_sensor_update(self, sensor: Sensor) -> None:
        self.schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._sensor.on_update.subscribe(self._handle_sensor_update)

    async def async_will_remove_from_hass(self) -> None:
        await super().async_will_remove_from_hass()
        self._sensor.on_update.unsubscribe(self._handle_sensor_update)
