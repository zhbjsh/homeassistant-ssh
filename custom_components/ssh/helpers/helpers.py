from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ssh_terminal_manager import Sensor

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.template import Template

if TYPE_CHECKING:
    from .base_entity import BaseSensorEntity
    from .coordinator import StateCoordinator


def get_command_renderer(hass: HomeAssistant) -> Callable:
    def renderer(command_string):
        template = Template(command_string, hass)
        return template.async_render(parse_result=False)

    return renderer


def get_value_renderer(hass: HomeAssistant, value_template: str) -> Callable:
    def renderer(value: str):
        template = Template(value_template, hass)
        return template.async_render(variables={"value": value}, parse_result=False)

    return renderer


def get_child_added_listener(
    hass: HomeAssistant,
    platform: EntityPlatform,
    state_coordinator: StateCoordinator,
    config_entry: ConfigEntry,
    cls: type[BaseSensorEntity],
) -> Callable:
    def listener(parent: Sensor, child: Sensor):
        entity = next(
            (
                entity
                for entity in platform.entities.values()
                if isinstance(entity, cls) and entity.key == child.key
            ),
            None,
        )

        if entity:
            state_coordinator.logger.warning(
                "%s instance with key %s exists already",
                cls.__name__,
                child.key,
            )
            return

        entity = cls(state_coordinator, config_entry, child)
        hass.add_job(platform.async_add_entities, [entity])

    return listener


def get_child_removed_listener(
    hass: HomeAssistant,
    platform: EntityPlatform,
    state_coordinator: StateCoordinator,
    cls: type[BaseSensorEntity],
) -> Callable:
    def listener(parent: Sensor, child: Sensor):
        entity = next(
            (
                entity
                for entity in platform.entities.values()
                if isinstance(entity, cls) and entity.key == child.key
            ),
            None,
        )

        if entity is None:
            state_coordinator.logger.warning(
                "%s instance with key %s doesn't exist",
                cls.__name__,
                child.key,
            )
            return

        hass.add_job(platform.async_remove_entity, entity.entity_id)

    return listener
