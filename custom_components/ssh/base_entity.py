from typing import Any

from ssh_terminal_manager import ActionCommand, Sensor, State

from homeassistant.const import CONF_DEVICE_CLASS, CONF_ICON
from homeassistant.helpers.entity import DeviceInfo, generate_entity_id
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import CONF_ENTITY_REGISTRY_ENABLED_DEFAULT
from .coordinator import StateCoordinator
from .entry_data import EntryData


class BaseEntity(CoordinatorEntity):
    coordinator: StateCoordinator
    _entity_id_format: str
    _category = "base"
    _attr_has_entity_name = True

    def __init__(
        self,
        entry_data: EntryData,
        attributes: dict | None = None,
    ) -> None:
        super().__init__(entry_data.state_coordinator)
        self._manager = entry_data.manager
        self._config_entry = entry_data.config_entry
        self._attributes = attributes or {}
        self.entity_id = generate_entity_id(
            self._entity_id_format,
            f"{self._manager.name}_{self.key}" if self.key else self._manager.name,
            hass=self.coordinator.hass,
        )

    @property
    def key(self) -> str | None:
        return slugify(self.name) if self.name else None

    @property
    def unique_id(self) -> str:
        return (
            f"{self._config_entry.unique_id}_{self._category}_{self.key}"
            if self.key
            else self._config_entry.unique_id
        )

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(self._config_entry.domain, self._config_entry.unique_id)}
        )

    @property
    def device_class(self) -> Any | None:
        return self._attributes.get(CONF_DEVICE_CLASS)

    @property
    def icon(self) -> str | None:
        return self._attributes.get(CONF_ICON)

    @property
    def entity_registry_enabled_default(self) -> bool:
        return self._attributes.get(CONF_ENTITY_REGISTRY_ENABLED_DEFAULT, True)

    @property
    def available(self) -> bool:
        return self._manager.can_execute

    def _handle_manager_state_change(self, state: State) -> None:
        self.schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._manager.state.on_change.subscribe(self._handle_manager_state_change)

    async def async_will_remove_from_hass(self) -> None:
        self._manager.state.on_change.unsubscribe(self._handle_manager_state_change)
        await super().async_will_remove_from_hass()


class BaseActionEntity(BaseEntity):
    _category = "action"

    def __init__(
        self,
        entry_data: EntryData,
        command: ActionCommand,
    ) -> None:
        self._command = command
        super().__init__(entry_data, command.attributes)

    @property
    def key(self) -> str:
        return self._command.key

    @property
    def name(self) -> str | None:
        return self._command.name


class BaseSensorEntity(BaseEntity):
    _category = "sensor"

    def __init__(
        self,
        entry_data: EntryData,
        sensor: Sensor,
    ) -> None:
        self._sensor = sensor
        super().__init__(entry_data, sensor.attributes)

    @property
    def key(self) -> str:
        return self._sensor.key

    @property
    def name(self) -> str | None:
        return self._sensor.name

    def _handle_sensor_update(self, sensor: Sensor) -> None:
        self.schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._sensor.on_update.subscribe(self._handle_sensor_update)

    async def async_will_remove_from_hass(self) -> None:
        self._sensor.on_update.unsubscribe(self._handle_sensor_update)
        await super().async_will_remove_from_hass()
