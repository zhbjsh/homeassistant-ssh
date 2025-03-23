"""Platform for switch integration."""

from __future__ import annotations

from typing import Any

from ssh_terminal_manager import BinarySensor

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import BaseEntity, BaseSensorEntity
from .const import CONF_POWER_BUTTON
from .entry_data import EntryData
from .helpers import get_child_add_handler, get_child_remove_handler


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    entry_data: EntryData = hass.data[entry.domain][entry.entry_id]
    entities = await async_get_entities(hass, entry_data)

    if not entry.options[CONF_POWER_BUTTON]:
        entities.append(PowerEntity(entry_data))

    async_add_entities(entities)


async def async_get_entities(
    hass: HomeAssistant,
    entry_data: EntryData,
) -> list[SwitchEntity]:
    """Get switch entities."""
    platform = entity_platform.async_get_current_platform()
    handle_child_add = get_child_add_handler(hass, platform, entry_data, Entity)
    handle_child_remove = get_child_remove_handler(hass, platform, entry_data, Entity)
    ignored_keys = entry_data.ignored_sensor_keys
    entities = []

    for sensor in entry_data.manager.sensors_by_key.values():
        if not (isinstance(sensor, BinarySensor) and sensor.controllable):
            continue
        if ignored_keys and sensor.key in ignored_keys:
            continue
        if sensor.dynamic:
            sensor.on_child_add.subscribe(handle_child_add)
            sensor.on_child_remove.subscribe(handle_child_remove)
            continue
        entities.append(Entity(entry_data, sensor))

    return entities


class Entity(BaseSensorEntity, SwitchEntity):
    _entity_id_format = ENTITY_ID_FORMAT
    _sensor: BinarySensor

    @property
    def is_on(self) -> bool | None:
        return self._sensor.value

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_sensor_value(self.key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_sensor_value(self.key, False)


class PowerEntity(BaseEntity, SwitchEntity):
    _entity_id_format = ENTITY_ID_FORMAT
    _attr_name = "Power"

    @property
    def icon(self) -> str:
        return "mdi:power"

    @property
    def is_on(self) -> bool | None:
        return self._manager.can_execute

    @property
    def available(self) -> bool:
        return self._manager.can_turn_on or self._manager.can_turn_off

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_turn_off()
