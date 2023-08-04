"""Platform for switch integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EntryData
from .base.switch import async_get_entities
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SSH switch platform."""
    entry_data: EntryData = hass.data[DOMAIN][entry.entry_id]
    entities = await async_get_entities(hass, entry_data)
    async_add_entities(entities)
