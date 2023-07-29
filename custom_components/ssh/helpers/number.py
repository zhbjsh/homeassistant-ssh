from __future__ import annotations

from ssh_terminal_manager import NumberSensor

from homeassistant.components.number import ENTITY_ID_FORMAT, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform

from . import EntryData
from .base_entity import BaseSensorEntity
from .helpers import get_child_added_listener, get_child_removed_listener


async def async_get_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    entry_data: EntryData,
) -> list[NumberEntity]:
    platform = entity_platform.async_get_current_platform()

    child_added_listener = get_child_added_listener(
        hass, platform, entry_data.state_coordinator, config_entry, Entity
    )

    child_removed_listener = get_child_removed_listener(
        hass, platform, entry_data.state_coordinator, Entity
    )

    entities = []

    for sensor in entry_data.manager.sensors_by_key.values():
        if not (isinstance(sensor, NumberSensor) and sensor.controllable):
            continue
        if sensor.dynamic:
            sensor.on_child_added.subscribe(child_added_listener)
            sensor.on_child_removed.subscribe(child_removed_listener)
            continue
        entities.append(Entity(entry_data.state_coordinator, config_entry, sensor))

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
        await self._manager.async_set_sensor_value(self.key, value)
