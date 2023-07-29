"""Platform for button integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EntryData
from .const import DOMAIN
from ha_ssh_helpers.button import PowerEntity, async_get_entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SSH button platform."""
    entry_data: EntryData = hass.data[DOMAIN][config_entry.entry_id]
    entities = await async_get_entities(hass, config_entry, entry_data)
    async_add_entities(
        [
            *entities,
            PowerEntity(entry_data.state_coordinator, config_entry),
        ]
    )
