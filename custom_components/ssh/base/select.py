from __future__ import annotations

from ssh_terminal_manager import TextSensor

from homeassistant.components.select import ENTITY_ID_FORMAT, SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform

from .base_entity import BaseSensorEntity
from .entry_data import EntryData
from .helpers import get_child_add_handler, get_child_remove_handler


async def async_get_entities(
    hass: HomeAssistant,
    entry_data: EntryData,
) -> list[SelectEntity]:
    platform = entity_platform.async_get_current_platform()
    handle_child_add = get_child_add_handler(hass, platform, entry_data, Entity)
    handle_child_remove = get_child_remove_handler(hass, platform, entry_data, Entity)
    entities = []

    for sensor in entry_data.manager.sensors_by_key.values():
        if not (
            isinstance(sensor, TextSensor) and sensor.controllable and sensor.options
        ):
            continue
        if sensor.dynamic:
            sensor.on_child_add.subscribe(handle_child_add)
            sensor.on_child_remove.subscribe(handle_child_remove)
            continue
        entities.append(Entity(entry_data, sensor))

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
