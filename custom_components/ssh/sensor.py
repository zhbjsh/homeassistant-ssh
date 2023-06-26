"""Platform for sensor integration."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from ssh_remote_control import DynamicSensor

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import EntryData
from .base_entity import BaseSensorEntity
from .const import CONF_SUGGESTED_UNIT_OF_MEASUREMENT, DOMAIN
from .helpers import get_child_added_listener, get_child_removed_listener


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SSH sensor platform."""
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
        if sensor.value_type is bool or sensor.is_controllable:
            continue
        if isinstance(sensor, DynamicSensor):
            sensor.on_child_added.subscribe(child_added_listener)
            sensor.on_child_removed.subscribe(child_removed_listener)
            continue
        entities.append(Entity(entry_data.state_coordinator, config_entry, sensor))

    async_add_entities(entities)


class Entity(BaseSensorEntity, SensorEntity):
    _entity_id_format = ENTITY_ID_FORMAT

    @property
    def state_class(self) -> SensorStateClass | None:
        if self._sensor.value_type in [int, float]:
            return SensorStateClass.MEASUREMENT
        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self._sensor.value_unit

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        return self._sensor.value

    @property
    def suggested_unit_of_measurement(self) -> str | None:
        return self._options.get(CONF_SUGGESTED_UNIT_OF_MEASUREMENT)
