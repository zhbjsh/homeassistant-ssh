"""Platform for select integration."""
from __future__ import annotations

from ssh_terminal_manager import TextSensor

from homeassistant.components.select import ENTITY_ID_FORMAT, SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform

from . import EntryData
from .base_entity import BaseSensorEntity
from .helpers import get_child_added_listener, get_child_removed_listener


async def async_get_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    entry_data: EntryData,
) -> list[SelectEntity]:
    platform = entity_platform.async_get_current_platform()

    child_added_listener = get_child_added_listener(
        hass, platform, entry_data.state_coordinator, config_entry, Entity
    )

    child_removed_listener = get_child_removed_listener(
        hass, platform, entry_data.state_coordinator, Entity
    )

    entities = []

    for sensor in entry_data.manager.sensors_by_key.values():
        if not (
            isinstance(sensor, TextSensor) and sensor.controllable and sensor.options
        ):
            continue
        if sensor.dynamic:
            sensor.on_child_added.subscribe(child_added_listener)
            sensor.on_child_removed.subscribe(child_removed_listener)
            continue
        entities.append(Entity(entry_data.state_coordinator, config_entry, sensor))

    return entities


class Entity(BaseSensorEntity, SelectEntity):
    _entity_id_format = ENTITY_ID_FORMAT
    _sensor: TextSensor

    @property
    def options(self) -> list[str]:
        return self._sensor.options

    @property
    def current_option(self) -> str | None:
        return self._sensor.value

    async def async_select_option(self, option: str) -> None:
        await self._manager.async_set_sensor_value(self.key, option)
