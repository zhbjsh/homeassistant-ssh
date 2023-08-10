from __future__ import annotations

from collections.abc import Callable

from ssh_terminal_manager import Sensor, SensorKey

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.template import Template
from homeassistant.util.unit_conversion import InformationConverter

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
    sensors_by_key = entry_data.manager.sensors_by_key
    convert = InformationConverter().convert

    def get_hw_version() -> str | None:
        cpu_name = (
            sensor.last_known_value
            if (sensor := sensors_by_key.get(SensorKey.CPU_NAME))
            else None
        )
        cpu_count = (
            sensor.last_known_value
            if (sensor := sensors_by_key.get(SensorKey.CPU_COUNT))
            else None
        )
        machine_type = (
            sensor.last_known_value
            if (sensor := sensors_by_key.get(SensorKey.MACHINE_TYPE))
            else None
        )
        total_memory = (
            f"{round(convert(sensor.last_known_value, sensor.unit, 'GB'))} GB RAM"
            if (sensor := sensors_by_key.get(SensorKey.TOTAL_MEMORY))
            and sensor.last_known_value
            and sensor.unit
            else None
        )
        cpu_info = (
            f"{cpu_count} {cpu_name}"
            if cpu_count and cpu_name
            else f"{cpu_count} CPU(s)"
            if cpu_count
            else cpu_name
        )
        items = [item for item in (cpu_info, machine_type, total_memory) if item]
        return ", ".join(items) if items else None

    def get_sw_version() -> str | None:
        os_name = (
            sensor.last_known_value
            if (sensor := sensors_by_key.get(SensorKey.OS_NAME))
            else None
        )
        os_version = (
            sensor.last_known_value
            if (sensor := sensors_by_key.get(SensorKey.OS_VERSION))
            else None
        )
        return (
            f"{os_name} {os_version}"
            if os_name and os_version
            else os_name or os_version
        )

    def get_model() -> str | None:
        model = (
            sensor.last_known_value
            if (sensor := sensors_by_key.get(SensorKey.MODEL))
            else None
        )
        hardware = (
            sensor.last_known_value
            if (sensor := sensors_by_key.get(SensorKey.HARDWARE))
            else None
        )
        return model or hardware

    @callback
    def async_update_device_info():
        device_registry.async_update_device(
            device_id,
            hw_version=get_hw_version(),
            sw_version=get_sw_version(),
            model=get_model(),
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
