"""Platform for update integration."""

from __future__ import annotations

from typing import Any

from ssh_terminal_manager import VersionSensor

from homeassistant.components.update import (
    ENTITY_ID_FORMAT,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import BaseSensorEntity
from .entry_data import EntryData
from .helpers import get_child_add_handler, get_child_remove_handler


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the update platform."""
    entry_data: EntryData = hass.data[entry.domain][entry.entry_id]
    entities = await async_get_entities(hass, entry_data)
    async_add_entities(entities)


async def async_get_entities(
    hass: HomeAssistant,
    entry_data: EntryData,
) -> list[UpdateEntity]:
    """Get update entities."""
    platform = entity_platform.async_get_current_platform()
    handle_child_add = get_child_add_handler(hass, platform, entry_data, Entity)
    handle_child_remove = get_child_remove_handler(hass, platform, entry_data, Entity)
    ignored_keys = entry_data.ignored_sensor_keys
    entities = []

    for sensor in entry_data.manager.sensors_by_key.values():
        if not (isinstance(sensor, VersionSensor) and sensor.latest):
            continue
        if ignored_keys and sensor.key in ignored_keys:
            continue
        if sensor.dynamic:
            sensor.on_child_add.subscribe(handle_child_add)
            sensor.on_child_remove.subscribe(handle_child_remove)
            continue
        entities.append(Entity(entry_data, sensor))

    return entities


class Entity(BaseSensorEntity, UpdateEntity):
    _entity_id_format = ENTITY_ID_FORMAT
    _sensor: VersionSensor

    def __init__(self, entry_data: EntryData, sensor: VersionSensor) -> None:
        super().__init__(entry_data, sensor)
        self._latest_sensor = self._manager.sensors_by_key.get(sensor.latest)

    @property
    def supported_features(self) -> UpdateEntityFeature:
        if self._sensor.controllable:
            return UpdateEntityFeature.INSTALL
        return UpdateEntityFeature(0)

    @property
    def title(self) -> str:
        return self.name

    @property
    def installed_version(self) -> str:
        return self._sensor.value

    @property
    def latest_version(self) -> str | None:
        return self._latest_sensor.value if self._latest_sensor else None

    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        return latest_version != installed_version

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        value = version or self.latest_version
        await self.coordinator.async_set_sensor_value(self.key, value)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        if self._latest_sensor:
            self._latest_sensor.on_update.subscribe(self._handle_sensor_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._latest_sensor:
            self._latest_sensor.on_update.unsubscribe(self._handle_sensor_update)

        await super().async_will_remove_from_hass()
