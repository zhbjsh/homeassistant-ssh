"""Config flow for SSH integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
import re
from typing import Any

from ssh_remote_control import (
    DEFAULT_ADD_HOST_KEYS,
    DEFAULT_SSH_PORT,
    Collection,
    OfflineError,
    Remote,
    SSHAuthError,
    SSHConnectError,
    SSHHostKeyUnknownError,
    default_collections,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_COMMAND,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_DEVICE_CLASS,
    CONF_ENABLED,
    CONF_HOST,
    CONF_ICON,
    CONF_MAC,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_MODE,
    CONF_NAME,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    ObjectSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util import slugify

from .const import (
    CONF_ACTION_COMMANDS,
    CONF_ADD_HOST_KEYS,
    CONF_ALLOW_TURN_OFF,
    CONF_COMMAND_SET,
    CONF_COMMAND_TIMEOUT,
    CONF_DEFAULT_COMMANDS,
    CONF_DYNAMIC,
    CONF_INTEGER,
    CONF_KEY,
    CONF_OPTIONS,
    CONF_PATTERN,
    CONF_PING_TIMEOUT,
    CONF_SENSOR_COMMANDS,
    CONF_SENSORS,
    CONF_SEPARATOR,
    CONF_SSH_HOST_KEYS_FILE,
    CONF_SSH_KEY_FILE,
    CONF_SSH_PASSWORD,
    CONF_SSH_PORT,
    CONF_SSH_TIMEOUT,
    CONF_SSH_USER,
    CONF_SUGGESTED_DISPLAY_PRECISION,
    CONF_SUGGESTED_UNIT_OF_MEASUREMENT,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)
from .converter import (
    get_action_command_config,
    get_collection,
    get_sensor_command_config,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_UPDATE_INTERVAL = 30
DEFAULT_HOST_KEYS_FILENAME = ".ssh_known_hosts"

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_TYPE): str,
        vol.Optional(CONF_NAME): str,
        vol.Optional(CONF_KEY): str,
        vol.Optional(CONF_DYNAMIC): bool,
        vol.Optional(CONF_SEPARATOR): str,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): str,
        vol.Optional(CONF_VALUE_TEMPLATE): str,
        vol.Optional(CONF_COMMAND_SET): str,
        vol.Optional(CONF_SUGGESTED_UNIT_OF_MEASUREMENT): str,
        vol.Optional(CONF_SUGGESTED_DISPLAY_PRECISION): int,
        vol.Optional(CONF_MODE): str,
        vol.Optional(CONF_DEVICE_CLASS): str,
        vol.Optional(CONF_ICON): str,
        vol.Optional(CONF_ENABLED): bool,
    }
)

TEXT_SENSOR_SCHEMA = SENSOR_SCHEMA.extend(
    {
        vol.Optional(CONF_MINIMUM): int,
        vol.Optional(CONF_MAXIMUM): int,
        vol.Optional(CONF_PATTERN): str,
        vol.Optional(CONF_OPTIONS): list,
    }
)

NUMBER_SENSOR_SCHEMA = SENSOR_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "number",
        vol.Optional(CONF_INTEGER): bool,
        vol.Optional(CONF_MINIMUM): vol.Coerce(float),
        vol.Optional(CONF_MAXIMUM): vol.Coerce(float),
    }
)

BINARY_SENSOR_SCHEMA = SENSOR_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "binary",
        vol.Optional(CONF_COMMAND_ON): str,
        vol.Optional(CONF_COMMAND_OFF): str,
        vol.Optional(CONF_PAYLOAD_ON): str,
        vol.Optional(CONF_PAYLOAD_OFF): str,
    }
)

COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COMMAND): str,
        vol.Optional(CONF_TIMEOUT): int,
    }
)

ACTION_COMMAND_SCHEMA = COMMAND_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): str,
        vol.Optional(CONF_KEY): str,
        vol.Optional(CONF_DEVICE_CLASS): str,
        vol.Optional(CONF_ICON): str,
        vol.Optional(CONF_ENABLED): bool,
    }
)

SENSOR_COMMAND_SCHEMA = COMMAND_SCHEMA.extend(
    {
        vol.Optional(CONF_SCAN_INTERVAL): int,
        vol.Required(CONF_SENSORS): vol.Schema(
            [
                vol.Any(
                    TEXT_SENSOR_SCHEMA,
                    NUMBER_SENSOR_SCHEMA,
                    BINARY_SENSOR_SCHEMA,
                )
            ]
        ),
    }
)

DEFAULT_COMMANDS_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        mode=SelectSelectorMode.DROPDOWN,
        options=[
            *[
                SelectOptionDict(value=key, label=value.name)
                for key, value in default_collections.__dict__.items()
                if isinstance(value, Collection)
            ],
            SelectOptionDict(value="none", label="None"),
        ],
    )
)


async def validate_name(hass: HomeAssistant, name: str):
    """Validate the name doesn't exist yet."""
    name = name.strip()

    for entry in hass.config_entries.async_entries(DOMAIN):
        if slugify(entry.data[CONF_NAME]) == slugify(name):
            raise NameExistsError

    return name


def validate_mac_address(mac_address: str):
    """Validate the mac address has the correct format."""
    mac_address = mac_address.strip()

    pattern = (
        "^([0-9A-Fa-f]{2}[:-])"
        + "{5}([0-9A-Fa-f]{2})|"
        + "([0-9a-fA-F]{4}\\."
        + "[0-9a-fA-F]{4}\\."
        + "[0-9a-fA-F]{4})$"
    )

    if not re.fullmatch(pattern, mac_address):
        raise MACAddressInvalidError

    return mac_address


def validate_options(hass: HomeAssistant, options: dict[str, Any]) -> dict[str, Any]:
    """Validate the options user input."""
    get_collection(hass, options)
    return options


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the config user input."""
    remote = Remote(
        data[CONF_HOST],
        add_host_keys=data[CONF_ADD_HOST_KEYS],
        ssh_port=data[CONF_SSH_PORT],
        ssh_user=data.get(CONF_SSH_USER),
        ssh_password=data.get(CONF_SSH_PASSWORD),
        ssh_key_file=data.get(CONF_SSH_KEY_FILE),
        ssh_host_keys_file=data.get(CONF_SSH_HOST_KEYS_FILE),
        collection=(
            getattr(default_collections, key)
            if (key := data[CONF_DEFAULT_COMMANDS]) != "none"
            else None
        ),
        logger=_LOGGER,
    )

    await remote.async_update_state(raise_errors=True)
    await remote.async_disconnect()

    if mac_address := remote.mac_address:
        _LOGGER.info("%s: Detected MAC address: %s", remote.host, mac_address)
        try:
            data[CONF_MAC] = validate_mac_address(mac_address)
        except MACAddressInvalidError:
            _LOGGER.info("%s: Detected MAC address is invalid", remote.host)

    if hostname := remote.hostname:
        _LOGGER.info("%s: Detected hostname: %s", remote.host, hostname)
        try:
            data[CONF_NAME] = await validate_name(hass, hostname)
        except NameExistsError:
            _LOGGER.info("%s: Detected hostname exists already", remote.host)

    options = {
        CONF_ALLOW_TURN_OFF: remote.allow_turn_off,
        CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
        CONF_PING_TIMEOUT: remote.ping_timeout,
        CONF_SSH_TIMEOUT: remote.ssh_timeout,
        CONF_COMMAND_TIMEOUT: remote.command_timeout,
        CONF_ACTION_COMMANDS: [
            get_action_command_config(command) for command in remote.action_commands
        ],
        CONF_SENSOR_COMMANDS: [
            get_sensor_command_config(command) for command in remote.sensor_commands
        ],
    }

    return data, options


class ListSelector(ObjectSelector):
    """Selector for a list."""

    def __init__(
        self, schema: vol.Schema, config: Mapping[str, Any] | None = None
    ) -> None:
        super().__init__(config)
        self._schema = schema

    def __call__(self, data: Any) -> Any:
        return [self._schema(element) for element in data]


class OptionsFlow(config_entries.OptionsFlow):
    """Handle a options flow for SSH."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry
        self._data = config_entry.options.copy()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data = user_input
            try:
                options = validate_options(self.hass, user_input)
            except ValueError:
                errors["base"] = "name_key_error"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ALLOW_TURN_OFF,
                        default=self._data[CONF_ALLOW_TURN_OFF],
                    ): bool,
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=self._data[CONF_UPDATE_INTERVAL],
                    ): int,
                    vol.Required(
                        CONF_PING_TIMEOUT,
                        default=self._data[CONF_PING_TIMEOUT],
                    ): int,
                    vol.Required(
                        CONF_SSH_TIMEOUT,
                        default=self._data[CONF_SSH_TIMEOUT],
                    ): int,
                    vol.Required(
                        CONF_COMMAND_TIMEOUT,
                        default=self._data[CONF_COMMAND_TIMEOUT],
                    ): int,
                    vol.Required(
                        CONF_ACTION_COMMANDS,
                        default=self._data[CONF_ACTION_COMMANDS],
                    ): ListSelector(ACTION_COMMAND_SCHEMA),
                    vol.Required(
                        CONF_SENSOR_COMMANDS,
                        default=self._data[CONF_SENSOR_COMMANDS],
                    ): ListSelector(SENSOR_COMMAND_SCHEMA),
                }
            ),
        )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SSH."""

    VERSION = 1

    def __init__(self) -> None:
        self._reauth_entry: ConfigEntry | None = None
        self._data: dict[str, Any] = {}
        self._options: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data = user_input
            try:
                self._data, self._options = await validate_input(self.hass, user_input)
            except PermissionError:
                errors["base"] = "permission_error"
            except OfflineError:
                errors["base"] = "offline_error"
            except SSHHostKeyUnknownError:
                errors["base"] = "ssh_host_key_unknown_error"
            except SSHAuthError:
                errors["base"] = "ssh_auth_error"
            except SSHConnectError:
                errors["base"] = "ssh_connect_error"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if not self._reauth_entry:
                    return await self.async_step_mac_address()
                data = {
                    **self._data,
                    CONF_MAC: self._reauth_entry[CONF_MAC],
                    CONF_NAME: self._reauth_entry[CONF_NAME],
                }
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data=data,
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ADD_HOST_KEYS,
                        default=self._data.get(
                            CONF_ADD_HOST_KEYS, DEFAULT_ADD_HOST_KEYS
                        ),
                    ): bool,
                    vol.Required(
                        CONF_HOST,
                        default=self._data.get(CONF_HOST, vol.UNDEFINED),
                    ): str,
                    vol.Required(
                        CONF_DEFAULT_COMMANDS,
                        default=self._data.get(CONF_DEFAULT_COMMANDS, vol.UNDEFINED),
                    ): DEFAULT_COMMANDS_SELECTOR,
                    vol.Required(
                        CONF_SSH_PORT,
                        default=self._data.get(CONF_SSH_PORT, DEFAULT_SSH_PORT),
                    ): int,
                    vol.Optional(
                        CONF_SSH_USER,
                        default=self._data.get(CONF_SSH_USER, vol.UNDEFINED),
                    ): str,
                    vol.Optional(
                        CONF_SSH_PASSWORD,
                        default=self._data.get(CONF_SSH_PASSWORD, vol.UNDEFINED),
                    ): str,
                    vol.Optional(
                        CONF_SSH_KEY_FILE,
                        default=self._data.get(CONF_SSH_KEY_FILE, vol.UNDEFINED),
                    ): str,
                    vol.Optional(
                        CONF_SSH_HOST_KEYS_FILE,
                        default=self._data.get(
                            CONF_SSH_HOST_KEYS_FILE,
                            f"{self.hass.config.config_dir}/{DEFAULT_HOST_KEYS_FILENAME}",
                        ),
                    ): str,
                }
            ),
        )

    async def async_step_mac_address(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the mac_address step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data[CONF_MAC] = user_input[CONF_MAC]
            try:
                self._data[CONF_MAC] = validate_mac_address(user_input[CONF_MAC])
            except MACAddressInvalidError:
                errors["base"] = "mac_address_invalid_error"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                unique_id = format_mac(self._data[CONF_MAC])
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return await self.async_step_name()

        return self.async_show_form(
            step_id="mac_address",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MAC, default=self._data.get(CONF_MAC, vol.UNDEFINED)
                    ): str
                }
            ),
        )

    async def async_step_name(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the name step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data[CONF_NAME] = user_input[CONF_NAME]
            try:
                self._data[CONF_NAME] = await validate_name(
                    self.hass, user_input[CONF_NAME]
                )
            except NameExistsError:
                errors["base"] = "name_exists_error"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                title = self._data[CONF_NAME]
                return self.async_create_entry(
                    title=title, data=self._data, options=self._options
                )

        return self.async_show_form(
            step_id="name",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=self._data.get(CONF_NAME, vol.UNDEFINED)
                    ): str
                }
            ),
        )

    async def async_step_reauth(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon a SSH authentication error."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        self._data = self._reauth_entry.data.copy()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=vol.Schema({})
            )
        return await self.async_step_user()


class NameExistsError(Exception):
    """Error to indicate name exists already."""


class MACAddressInvalidError(Exception):
    """Error to indicate MAC address is invalid."""
