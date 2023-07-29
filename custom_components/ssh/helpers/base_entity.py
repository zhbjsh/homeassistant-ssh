from typing import Any

from ssh_terminal_manager import ActionCommand, Sensor, State

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_CLASS, CONF_ICON
from homeassistant.helpers.entity import DeviceInfo, generate_entity_id
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import CONF_ENTITY_REGISTRY_ENABLED_DEFAULT
from .coordinator import StateCoordinator


class BaseEntity(CoordinatorEntity):
    coordinator: StateCoordinator
    _entity_id_format: str
    _category = "base"
    _attr_has_entity_name = True

    def __init__(
        self,
        state_coordinator: StateCoordinator,
        config_entry: ConfigEntry,
        attributes: dict | None = None,
    ) -> None:
        super().__init__(state_coordinator)
        self._manager = state_coordinator.manager
        self._config_entry = config_entry
        self._attributes = attributes or {}
        self.entity_id = generate_entity_id(
            self._entity_id_format,
            f"{self._manager.name}_{self._id}",
            hass=self.coordinator.hass,
        )

    @property
    def _id(self) -> str:
        return slugify(self.name)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(self._config_entry.domain, self._config_entry.unique_id)},
            name=self._config_entry.title,
            sw_version=(
                f"{self._manager.os_name} {self._manager.os_version}"
                if self._manager.os_name and self._manager.os_version
                else None
            ),
            hw_version=self._manager.machine_type,
        )

    @property
    def unique_id(self) -> str:
        return f"{self._config_entry.unique_id}_{self._category}_{self._id}"

    @property
    def device_class(self) -> Any | None:
        return self._attributes.get(CONF_DEVICE_CLASS)

    @property
    def icon(self) -> str | None:
        return self._attributes.get(CONF_ICON)

    @property
    def entity_registry_enabled_default(self) -> bool:
        return self._attributes.get(CONF_ENTITY_REGISTRY_ENABLED_DEFAULT, True)

    def _handle_manager_state_change(self, state: State) -> None:
        self.schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        self._manager.state.on_change.subscribe(self._handle_manager_state_change)

    async def async_will_remove_from_hass(self) -> None:
        self._manager.state.on_change.unsubscribe(self._handle_manager_state_change)


class BaseActionEntity(BaseEntity):
    _category = "action"

    def __init__(
        self,
        state_coordinator: StateCoordinator,
        config_entry: ConfigEntry,
        command: ActionCommand,
    ) -> None:
        self._command = command
        super().__init__(state_coordinator, config_entry, command.attributes)

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
        return self._manager.state.connected


class BaseSensorEntity(BaseEntity):
    _category = "sensor"

    def __init__(
        self,
        state_coordinator: StateCoordinator,
        config_entry: ConfigEntry,
        sensor: Sensor,
    ) -> None:
        self._sensor = sensor
        super().__init__(state_coordinator, config_entry, sensor.attributes)

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
        return self._manager.state.connected

    def _handle_sensor_update(self, sensor: Sensor) -> None:
        self.schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._sensor.on_update.subscribe(self._handle_sensor_update)

    async def async_will_remove_from_hass(self) -> None:
        await super().async_will_remove_from_hass()
        self._sensor.on_update.unsubscribe(self._handle_sensor_update)
