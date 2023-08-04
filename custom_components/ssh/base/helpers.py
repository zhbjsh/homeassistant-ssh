from __future__ import annotations

from collections.abc import Callable

from ssh_terminal_manager import Sensor

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.template import Template

from .base_entity import BaseSensorEntity
from .entry_data import EntryData


def get_command_renderer(hass: HomeAssistant) -> Callable:
    def async_renderer(command_string):
        template = Template(command_string, hass)
        return template.async_render(parse_result=False)

    return async_renderer


def get_value_renderer(hass: HomeAssistant, value_template: str) -> Callable:
    def async_renderer(value: str):
        template = Template(value_template, hass)
        return template.async_render(variables={"value": value}, parse_result=False)

    return async_renderer


def get_device_sensor_update_handler(
    hass: HomeAssistant,
    entry_data: EntryData,
    device_registry: DeviceRegistry,
) -> Callable:
    device_id = entry_data.device_entry.id
    manager = entry_data.manager

    @callback
    def async_update_device_info():
        device_registry.async_update_device(
            device_id,
            hw_version=manager.machine_type,
            sw_version=(
                f"{manager.os_name} {manager.os_version}"
                if manager.os_name and manager.os_version
                else None
            ),
        )

    def handler(sensor: Sensor):
        if sensor.value is not None:
            hass.add_job(async_update_device_info)

    return handler


def get_child_add_handler(
    hass: HomeAssistant,
    platform: EntityPlatform,
    entry_data: EntryData,
    cls: type[BaseSensorEntity],
) -> Callable:
    def handler(parent: Sensor, child: Sensor):
        entity = next(
            (
                entity
                for entity in platform.entities.values()
                if isinstance(entity, cls) and entity.key == child.key
            ),
            None,
        )

        if entity:
            entry_data.state_coordinator.logger.warning(
                "%s: %s instance with key %s exists already",
                entry_data.state_coordinator.name,
                cls.__name__,
                child.key,
            )
            return

        hass.add_job(platform.async_add_entities, [cls(entry_data, child)])

    return handler


def get_child_remove_handler(
    hass: HomeAssistant,
    platform: EntityPlatform,
    entry_data: EntryData,
    cls: type[BaseSensorEntity],
) -> Callable:
    def handler(parent: Sensor, child: Sensor):
        entity = next(
            (
                entity
                for entity in platform.entities.values()
                if isinstance(entity, cls) and entity.key == child.key
            ),
            None,
        )

        if entity is None:
            entry_data.state_coordinator.logger.warning(
                "%s: %s instance with key %s doesn't exist",
                entry_data.state_coordinator.name,
                cls.__name__,
                child.key,
            )
            return

        hass.add_job(platform.async_remove_entity, entity.entity_id)

    return handler
