"""The SSH integration."""
from __future__ import annotations

import logging

from ssh_terminal_manager import SSHManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from ha_ssh_helpers import PLATFORMS, EntryData, async_initialize
from ha_ssh_helpers.const import (
    CONF_ALLOW_TURN_OFF,
    CONF_COMMAND_TIMEOUT,
    CONF_HOST_KEYS_FILENAME,
    CONF_KEY_FILENAME,
)
from ha_ssh_helpers.converter import get_collection

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SSH from a config entry."""
    data = entry.data
    options = entry.options

    manager = SSHManager(
        data[CONF_HOST],
        name=data[CONF_NAME],
        port=data[CONF_PORT],
        username=data.get(CONF_USERNAME),
        password=data.get(CONF_PASSWORD),
        key_filename=data.get(CONF_KEY_FILENAME),
        host_keys_filename=data.get(CONF_HOST_KEYS_FILENAME),
        allow_turn_off=options[CONF_ALLOW_TURN_OFF],
        command_timeout=options[CONF_COMMAND_TIMEOUT],
        collection=get_collection(hass, options),
        logger=_LOGGER,
    )

    manager.set_mac_address(data[CONF_MAC])
    await async_initialize(hass, entry, manager, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry_data: EntryData = hass.data[DOMAIN].pop(entry.entry_id)
        entry_data.state_coordinator.stop()

        for coordinator in entry_data.command_coordinators:
            coordinator.stop()

        await entry_data.manager.async_disconnect()

    return unload_ok
