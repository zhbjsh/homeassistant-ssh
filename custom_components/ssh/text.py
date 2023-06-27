"""Platform for text integration."""
from __future__ import annotations

from ssh_remote_control import DynamicSensor

from homeassistant.components.text import ENTITY_ID_FORMAT, TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EntryData
from .base_entity import BaseSensorEntity
from .const import DOMAIN
from .helpers import get_child_added_listener, get_child_removed_listener


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SSH text platform."""
    platform = entity_platform.async_get_current_platform()
    entry_data: EntryData = hass.data[DOMAIN][config_entry.entry_id]

    child_added_listener = get_child_added_listener(
        hass, platform, entry_data.state_coordinator, config_entry, Entity
    )

    child_removed_listener = get_child_removed_listener(
        hass, platform, entry_data.state_coordinator, Entity
    )

    entities = []

    for sensor in entry_data.remote.sensors_by_key.values():
        if not (sensor.value_type is str and sensor.is_controllable):
            continue
        if isinstance(sensor, DynamicSensor):
            sensor.on_child_added.subscribe(child_added_listener)
            sensor.on_child_removed.subscribe(child_removed_listener)
            continue
        entities.append(Entity(entry_data.state_coordinator, config_entry, sensor))

    async_add_entities(entities)


class Entity(BaseSensorEntity, TextEntity):
    _entity_id_format = ENTITY_ID_FORMAT

    @property
    def native_value(self) -> str | None:
        return self._sensor.value

    @property
    def native_max(self) -> int:
        if self._sensor.value_max is not None:
            return int(self._sensor.value_max)
        return 100

    @property
    def native_min(self) -> int:
        if self._sensor.value_min is not None:
            return int(self._sensor.value_min)
        return 0

    @property
    def pattern(self) -> str | None:
        return self._sensor.value_pattern

    @property
    def mode(self) -> TextMode:
        return self._options.get(CONF_MODE, TextMode.TEXT)

    async def async_set_value(self, value: str) -> None:
        await self._remote.async_set_sensor_value(self.key, value)
