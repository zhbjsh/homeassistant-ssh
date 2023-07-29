"""Config flow for SSH integration."""
from __future__ import annotations

import logging

from .const import DOMAIN
from .helpers.config_flow import ConfigFlow, OptionsFlow

_LOGGER = logging.getLogger(__name__)


class OptionsFlow(OptionsFlow, logger=_LOGGER):
    """Handle a options flow for SSH."""


class ConfigFlow(ConfigFlow, domain=DOMAIN, logger=_LOGGER):
    """Handle a config flow for SSH."""

    VERSION = 1
