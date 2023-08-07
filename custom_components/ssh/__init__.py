"""The SSH integration."""
from __future__ import annotations

import logging

from ssh_terminal_manager import ActionKey, SensorKey, SSHManager

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

from .base import (
    PLATFORMS,
    Converter,
    EntryData,
    async_initialize_entry,
    async_register_services,
    async_unload_entry,
)
from .base.const import (
    CONF_ALLOW_TURN_OFF,
    CONF_COMMAND_TIMEOUT,
    CONF_HOST_KEYS_FILENAME,
    CONF_KEY_FILENAME,
    CONF_UPDATE_INTERVAL,
)
from .const import DOMAIN

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
        collection=Converter(hass).get_collection(options),
        logger=_LOGGER,
    )

    manager.set_mac_address(data[CONF_MAC])

    await async_initialize_entry(
        hass,
        entry,
        PLATFORMS,
        manager,
        options[CONF_UPDATE_INTERVAL],
        ignored_action_keys=[ActionKey.TURN_OFF],
    )

    async_register_services(hass, DOMAIN)

    return True
