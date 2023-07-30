"""Config flow for SSH integration."""
from __future__ import annotations

import logging

from .base.config_flow import ConfigFlow, OptionsFlow
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class OptionsFlow(OptionsFlow, logger=_LOGGER):
    """Handle a options flow for SSH."""


class ConfigFlow(ConfigFlow, logger=_LOGGER, domain=DOMAIN):
    """Handle a config flow for SSH."""
