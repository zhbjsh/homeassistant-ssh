"""Platform for button integration."""

from __future__ import annotations

from ssh_terminal_manager import ActionKey

from homeassistant.components.button import ENTITY_ID_FORMAT, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import BaseActionEntity, BaseEntity
from .entry_data import EntryData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button platform."""
    entry_data: EntryData = hass.data[entry.domain][entry.entry_id]
    entities = await async_get_entities(hass, entry_data)
    async_add_entities(
        [
            *entities,
            PowerEntity(entry_data),
        ]
    )


async def async_get_entities(
    hass: HomeAssistant,
    entry_data: EntryData,
) -> list[ButtonEntity]:
    """Get button entities."""
    ignored_keys = entry_data.ignored_action_keys
    entities = []

    for command in entry_data.manager.action_commands:
        if command.required_variables:
            continue
        if ignored_keys and command.key in ignored_keys:
            continue
        entities.append(Entity(entry_data, command))

    return entities


class Entity(BaseActionEntity, ButtonEntity):
    _entity_id_format = ENTITY_ID_FORMAT

    async def async_press(self) -> None:
        if self.key == ActionKey.RESTART:
            await self.coordinator.async_restart()
            return
        await self._manager.async_run_action(self.key)


class PowerEntity(BaseEntity, ButtonEntity):
    _entity_id_format = ENTITY_ID_FORMAT
    _attr_name = "Power"

    @property
    def icon(self) -> str:
        return "mdi:power"

    @property
    def available(self) -> bool:
        if not self._manager.state.online:
            return True
        if (
            self._manager.state.connected
            and self._manager.allow_turn_off
            and ActionKey.TURN_OFF in self._manager.action_commands_by_key
        ):
            return True
        return False

    async def async_press(self) -> None:
        if not self._manager.state.online:
            await self.coordinator.async_turn_on()

        elif self._manager.state.connected:
            await self.coordinator.async_turn_off()
