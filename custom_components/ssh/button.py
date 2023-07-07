"""Platform for button integration."""
from __future__ import annotations

from ssh_terminal_manager import ActionKey

from homeassistant.components.button import ENTITY_ID_FORMAT, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EntryData
from .base_entity import BaseActionEntity, BaseEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SSH sensor platform."""
    entry_data: EntryData = hass.data[DOMAIN][config_entry.entry_id]

    entities = [PowerEntity(entry_data.state_coordinator, config_entry)]

    for command in entry_data.manager.action_commands:
        if command.get_variable_keys(entry_data.manager):
            continue
        if command.key == ActionKey.TURN_OFF:
            continue
        entities.append(Entity(entry_data.state_coordinator, config_entry, command))

    async_add_entities(entities)


class Entity(BaseActionEntity, ButtonEntity):
    _entity_id_format = ENTITY_ID_FORMAT

    async def async_press(self) -> None:
        await self._manager.async_run_action(self.key)


class PowerEntity(BaseEntity, ButtonEntity):
    _entity_id_format = ENTITY_ID_FORMAT
    _attr_name = "Power"

    @property
    def icon(self) -> str:
        return "mdi:power"

    @property
    def available(self) -> bool:
        if not self._manager.state.online and self._manager.mac_address:
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
            await self._manager.async_turn_on()

        elif self._manager.state.connected:
            await self._manager.async_turn_off()
