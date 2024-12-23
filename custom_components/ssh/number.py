"""Platform for number integration."""

from __future__ import annotations

from ssh_terminal_manager import NumberSensor

from homeassistant.components.number import ENTITY_ID_FORMAT, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import BaseSensorEntity
from .entry_data import EntryData
from .helpers import get_child_add_handler, get_child_remove_handler


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform."""
    entry_data: EntryData = hass.data[entry.domain][entry.entry_id]
    entities = await async_get_entities(hass, entry_data)
    async_add_entities(entities)


async def async_get_entities(
    hass: HomeAssistant,
    entry_data: EntryData,
) -> list[NumberEntity]:
    """Get number entities."""
    platform = entity_platform.async_get_current_platform()
    handle_child_add = get_child_add_handler(hass, platform, entry_data, Entity)
    handle_child_remove = get_child_remove_handler(hass, platform, entry_data, Entity)
    ignored_keys = entry_data.ignored_sensor_keys
    entities = []

    for sensor in entry_data.manager.sensors_by_key.values():
        if not (isinstance(sensor, NumberSensor) and sensor.controllable):
            continue
        if ignored_keys and sensor.key in ignored_keys:
            continue
        if sensor.dynamic:
            sensor.on_child_add.subscribe(handle_child_add)
            sensor.on_child_remove.subscribe(handle_child_remove)
            continue
        entities.append(Entity(entry_data, sensor))

    return entities


class Entity(BaseSensorEntity, NumberEntity):
    _entity_id_format = ENTITY_ID_FORMAT
    _sensor: NumberSensor

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self._sensor.unit

    @property
    def native_value(self) -> int | float | None:
        return self._sensor.value

    @property
    def native_max_value(self) -> float:
        if self._sensor.maximum is not None:
            return float(self._sensor.maximum)
        return 100.0

    @property
    def native_min_value(self) -> float:
        if self._sensor.minimum is not None:
            return float(self._sensor.minimum)
        return 0.0

    @property
    def mode(self) -> NumberMode:
        return self._attributes.get(CONF_MODE, NumberMode.AUTO)

    async def async_set_native_value(self, value: float) -> None:
        if not self._sensor.float:
            value = int(value)
        await self.coordinator.async_set_sensor_value(self.key, value)
