"""Platform for sensor integration."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from ssh_terminal_manager import BinarySensor, NumberSensor, TextSensor

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.typing import StateType

from . import EntryData
from .base_entity import BaseSensorEntity
from .const import CONF_SUGGESTED_DISPLAY_PRECISION, CONF_SUGGESTED_UNIT_OF_MEASUREMENT
from .helpers import get_child_added_listener, get_child_removed_listener


async def async_get_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    entry_data: EntryData,
) -> list[SensorEntity]:
    platform = entity_platform.async_get_current_platform()

    child_added_listener = get_child_added_listener(
        hass, platform, entry_data.state_coordinator, config_entry, Entity
    )

    child_removed_listener = get_child_removed_listener(
        hass, platform, entry_data.state_coordinator, Entity
    )

    entities = []

    for sensor in entry_data.manager.sensors_by_key.values():
        if isinstance(sensor, BinarySensor) or sensor.controllable:
            continue
        if sensor.dynamic:
            sensor.on_child_added.subscribe(child_added_listener)
            sensor.on_child_removed.subscribe(child_removed_listener)
            continue
        entities.append(Entity(entry_data.state_coordinator, config_entry, sensor))

    return entities


class Entity(BaseSensorEntity, SensorEntity):
    _entity_id_format = ENTITY_ID_FORMAT
    _sensor: TextSensor | NumberSensor

    @property
    def state_class(self) -> SensorStateClass | None:
        if isinstance(self._sensor, NumberSensor):
            return SensorStateClass.MEASUREMENT
        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self._sensor.unit

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        return self._sensor.value

    @property
    def suggested_display_precision(self) -> int | None:
        return self._attributes.get(CONF_SUGGESTED_DISPLAY_PRECISION)

    @property
    def suggested_unit_of_measurement(self) -> str | None:
        return self._attributes.get(CONF_SUGGESTED_UNIT_OF_MEASUREMENT)
