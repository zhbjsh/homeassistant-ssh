"""Platform for binary sensor integration."""
from __future__ import annotations

from ssh_remote_control import DynamicSensor

from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EntryData
from .base_entity import BaseEntity, BaseSensorEntity
from .const import DOMAIN
from .helpers import get_child_added_listener, get_child_removed_listener


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SSH binary sensor platform."""
    platform = entity_platform.async_get_current_platform()
    entry_data: EntryData = hass.data[DOMAIN][config_entry.entry_id]

    child_added_listener = get_child_added_listener(
        hass, platform, entry_data.state_coordinator, config_entry, Entity
    )

    child_removed_listener = get_child_removed_listener(
        hass, platform, entry_data.state_coordinator, Entity
    )

    entities = [
        NetworkEntity(entry_data.state_coordinator, config_entry),
        SSHEntity(entry_data.state_coordinator, config_entry),
    ]

    for sensor in entry_data.remote.sensors_by_key.values():
        if sensor.value_type is not bool or sensor.is_controllable:
            continue
        if isinstance(sensor, DynamicSensor):
            sensor.on_child_added.subscribe(child_added_listener)
            sensor.on_child_removed.subscribe(child_removed_listener)
            continue
        entities.append(Entity(entry_data.state_coordinator, config_entry, sensor))

    async_add_entities(entities)


class Entity(BaseSensorEntity, BinarySensorEntity):
    _entity_id_format = ENTITY_ID_FORMAT

    @property
    def is_on(self) -> bool | None:
        return self._sensor.value


class NetworkEntity(BaseEntity, BinarySensorEntity):
    _entity_id_format = ENTITY_ID_FORMAT
    _attr_name = "Network"

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        return BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        return self._remote.state.is_online


class SSHEntity(BaseEntity, BinarySensorEntity):
    _entity_id_format = ENTITY_ID_FORMAT
    _attr_name = "SSH"

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        return BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        return self._remote.state.is_connected
