"""Platform for binary sensor integration."""

from __future__ import annotations

from ssh_terminal_manager import BinarySensor

from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import BaseEntity, BaseSensorEntity
from .entry_data import EntryData
from .helpers import get_child_add_handler, get_child_remove_handler


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    entry_data: EntryData = hass.data[entry.domain][entry.entry_id]
    entities = await async_get_entities(hass, entry_data)
    async_add_entities(
        [
            *entities,
            NetworkEntity(entry_data),
            SSHEntity(entry_data),
        ]
    )


async def async_get_entities(
    hass: HomeAssistant,
    entry_data: EntryData,
) -> list[BinarySensorEntity]:
    """Get binary sensor entities."""
    platform = entity_platform.async_get_current_platform()
    handle_child_add = get_child_add_handler(hass, platform, entry_data, Entity)
    handle_child_remove = get_child_remove_handler(hass, platform, entry_data, Entity)
    ignored_keys = entry_data.ignored_sensor_keys
    entities = []

    for sensor in entry_data.manager.sensors_by_key.values():
        if not isinstance(sensor, BinarySensor) or sensor.controllable:
            continue
        if ignored_keys and sensor.key in ignored_keys:
            continue
        if sensor.dynamic:
            sensor.on_child_add.subscribe(handle_child_add)
            sensor.on_child_remove.subscribe(handle_child_remove)
            continue
        entities.append(Entity(entry_data, sensor))

    return entities


class Entity(BaseSensorEntity, BinarySensorEntity):
    _entity_id_format = ENTITY_ID_FORMAT
    _sensor: BinarySensor

    @property
    def is_on(self) -> bool | None:
        return self._sensor.value


class NetworkEntity(BaseEntity, BinarySensorEntity):
    _entity_id_format = ENTITY_ID_FORMAT
    _attr_name = "Network status"

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        return BinarySensorDeviceClass.CONNECTIVITY

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self._manager.state.online


class SSHEntity(BaseEntity, BinarySensorEntity):
    _entity_id_format = ENTITY_ID_FORMAT
    _attr_name = "SSH status"

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        return BinarySensorDeviceClass.CONNECTIVITY

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self._manager.state.connected
