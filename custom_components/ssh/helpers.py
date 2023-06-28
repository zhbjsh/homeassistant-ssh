from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ssh_remote_control import Sensor

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.template import Template

if TYPE_CHECKING:
    from .base_entity import BaseSensorEntity
    from .coordinator import StateCoordinator


def get_command_renderer(hass: HomeAssistant) -> Callable:
    """Get command renderer."""

    def renderer(command_string):
        template = Template(command_string, hass)
        return template.render(parse_result=False)

    return renderer


def get_value_renderer(hass: HomeAssistant, value_template: str) -> Callable:
    """Get value renderer."""

    def renderer(value: str):
        template = Template(value_template, hass)
        return template.render(variables={"value": value}, parse_result=False)

    return renderer


def get_child_added_listener(
    hass: HomeAssistant,
    platform: EntityPlatform,
    state_coordinator: StateCoordinator,
    config_entry: ConfigEntry,
    cls: type[BaseSensorEntity],
) -> Callable:
    """Get child added listener."""

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
                "%s: %s instance with key %s exists already",
                state_coordinator.name,
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
    """Get child removed listener."""

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
                "%s: %s instance with key %s doesn't exist",
                state_coordinator.name,
                cls.__name__,
                child.key,
            )
            return

        hass.add_job(platform.async_remove_entity, entity.entity_id)

    return listener
