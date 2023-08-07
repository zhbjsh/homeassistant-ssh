"""Config flow for SSH integration."""
from __future__ import annotations

import logging

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback

from .base.config_flow import ConfigFlow, OptionsFlow
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class OptionsFlow(OptionsFlow, logger=_LOGGER):
    """Handle a options flow for SSH."""


class ConfigFlow(ConfigFlow, logger=_LOGGER, domain=DOMAIN):
    """Handle a config flow for SSH."""

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlow(config_entry)
