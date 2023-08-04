from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from ssh_terminal_manager import BinarySensor, NumberSensor, TextSensor

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.typing import StateType

from .base_entity import BaseSensorEntity
from .const import CONF_SUGGESTED_DISPLAY_PRECISION, CONF_SUGGESTED_UNIT_OF_MEASUREMENT
from .entry_data import EntryData
from .helpers import get_child_add_handler, get_child_remove_handler


async def async_get_entities(
    hass: HomeAssistant,
    entry_data: EntryData,
) -> list[SensorEntity]:
    platform = entity_platform.async_get_current_platform()
    handle_child_add = get_child_add_handler(hass, platform, entry_data, Entity)
    handle_child_remove = get_child_remove_handler(hass, platform, entry_data, Entity)
    entities = []

    for sensor in entry_data.manager.sensors_by_key.values():
        if isinstance(sensor, BinarySensor) or sensor.controllable:
            continue
        if sensor.dynamic:
            sensor.on_child_add.subscribe(handle_child_add)
            sensor.on_child_remove.subscribe(handle_child_remove)
            continue
        entities.append(Entity(entry_data, sensor))

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
