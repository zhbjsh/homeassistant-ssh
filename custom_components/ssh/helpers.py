from __future__ import annotations

from collections.abc import Callable

from ssh_terminal_manager import Sensor, SensorKey, SSHManager

from homeassistant.core import HomeAssistant
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


def get_device_info(manager: SSHManager) -> dict:
    convert = InformationConverter().convert

    def get_total_memory() -> str | None:
        sensor = manager.sensors_by_key.get(SensorKey.TOTAL_MEMORY)

        if not (sensor and sensor.last_known_value and sensor.unit):
            return None

        unit = "GB"
        value = convert(sensor.last_known_value, sensor.unit, unit)

        if value < 1:
            unit = "MB"
            value = convert(sensor.last_known_value, sensor.unit, unit)

        return f"{round(value)} {unit} RAM"

    def get_hw_version() -> str | None:
        machine_type = manager.machine_type
        cpu_cores = manager.cpu_cores
        cpu_name = manager.cpu_name
        cpu_info = (
            f"{cpu_cores} {cpu_name}"
            if cpu_cores and cpu_name
            else f"{cpu_cores} CPU(s)"
            if cpu_cores
            else cpu_name
        )
        total_memory = get_total_memory()
        items = [item for item in (cpu_info, machine_type, total_memory) if item]
        return ", ".join(items) if items else None

    def get_sw_version() -> str | None:
        os_name = manager.os_name
        os_version = manager.os_version
        os_release = manager.os_release
        return (
            os_release
            if os_release
            else f"{os_name} {os_version}"
            if os_name and os_version
            else os_name or os_version
        )

    def get_manufacturer() -> str | None:
        return manager.manufacturer

    def get_model() -> str | None:
        return (
            manager.device_model
            or manager.device_name
            or manager.cpu_model
            or manager.cpu_hardware
        )

    return {
        "hw_version": get_hw_version(),
        "sw_version": get_sw_version(),
        "manufacturer": get_manufacturer(),
        "model": get_model(),
    }


def get_device_sensor_update_handler(
    hass: HomeAssistant,
    entry_data: EntryData,
    device_registry: DeviceRegistry,
) -> Callable:
    def async_handler(sensor: Sensor):
        if sensor.value is not None:
            device_registry.async_update_device(
                entry_data.device_entry.id,
                **get_device_info(entry_data.manager),
            )

    return async_handler


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
