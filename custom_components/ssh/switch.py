"""Platform for switch integration."""
from __future__ import annotations

from typing import Any

from ssh_remote_control import DynamicSensor

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.config_entries import ConfigEntry
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
    """Set up the SSH switch platform."""
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
        if not (sensor.value_type is bool and sensor.is_controllable):
            continue
        if isinstance(sensor, DynamicSensor):
            sensor.on_child_added.subscribe(child_added_listener)
            sensor.on_child_removed.subscribe(child_removed_listener)
            continue
        entities.append(Entity(entry_data.state_coordinator, config_entry, sensor))

    async_add_entities(entities)


class Entity(BaseSensorEntity, SwitchEntity):
    _entity_id_format = ENTITY_ID_FORMAT

    @property
    def is_on(self) -> bool | None:
        return self._sensor.value

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._remote.async_set_sensor_value(self.key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._remote.async_set_sensor_value(self.key, False)
