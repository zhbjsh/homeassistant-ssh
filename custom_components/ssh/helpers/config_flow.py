"""Config flow for SSH integration."""
from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from ssh_terminal_manager import (
    DEFAULT_ADD_HOST_KEYS,
    DEFAULT_PORT,
    Collection,
    OfflineError,
    SSHAuthenticationError,
    SSHConnectError,
    SSHHostKeyUnknownError,
    SSHManager,
    default_collections,
)

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.button import (
    DEVICE_CLASSES_SCHEMA as BUTTON_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.number import (
    DEVICE_CLASSES_SCHEMA as NUMBER_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.number import NumberMode
from homeassistant.components.sensor import (
    DEVICE_CLASSES_SCHEMA as SENSOR_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.switch import (
    DEVICE_CLASSES_SCHEMA as SWITCH_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.text import TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_COMMAND,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_ICON,
    CONF_MAC,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_MODE,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
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
    CONF_ENTITY_REGISTRY_ENABLED_DEFAULT,
    CONF_FLOAT,
    CONF_HOST_KEYS_FILENAME,
    CONF_KEY,
    CONF_KEY_FILENAME,
    CONF_OPTIONS,
    CONF_PATTERN,
    CONF_SENSOR_COMMANDS,
    CONF_SENSORS,
    CONF_SEPARATOR,
    CONF_SUGGESTED_DISPLAY_PRECISION,
    CONF_SUGGESTED_UNIT_OF_MEASUREMENT,
    CONF_UPDATE_INTERVAL,
)
from .converter import (
    get_action_command_config,
    get_collection,
    get_sensor_command_config,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_UPDATE_INTERVAL = 30
DEFAULT_HOST_KEYS_FILENAME = "known_hosts"


def validate_sensor(data: dict) -> dict:
    sensor_type = data[CONF_TYPE]
    controllable = (
        data.get(CONF_COMMAND_SET)
        or data.get(CONF_COMMAND_ON)
        and data.get(CONF_COMMAND_OFF)
    )

    if sensor_type == "text":
        if not controllable:
            return TEXT_SENSOR_SCHEMA(data)
        return CONTROLLABLE_TEXT_SENSOR_SCHEMA(data)

    if sensor_type == "number":
        if not controllable:
            return NUMBER_SENSOR_SCHEMA(data)
        return CONTROLLABLE_NUMBER_SENSOR_SCHEMA(data)

    if sensor_type == "binary":
        if not controllable:
            return BINARY_SENSOR_SCHEMA(data)
        return CONTROLLABLE_BINARY_SENSOR_SCHEMA(data)

    if sensor_type == "placeholder":
        return data

    raise ValueError("Invalid sensor type")


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
        vol.Optional(CONF_DEVICE_CLASS): BUTTON_DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_ICON): str,
        vol.Optional(CONF_ENTITY_REGISTRY_ENABLED_DEFAULT): bool,
    }
)

SENSOR_COMMAND_SCHEMA = COMMAND_SCHEMA.extend(
    {
        vol.Optional(CONF_SCAN_INTERVAL): int,
        vol.Required(CONF_SENSORS): vol.Schema([validate_sensor]),
    }
)

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TYPE): vol.Any("text", "number", "binary", "placeholder"),
        vol.Optional(CONF_NAME): str,
        vol.Optional(CONF_KEY): str,
        vol.Optional(CONF_DYNAMIC): bool,
        vol.Optional(CONF_SEPARATOR): str,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): str,
        vol.Optional(CONF_VALUE_TEMPLATE): str,
        vol.Optional(CONF_COMMAND_SET): str,
        vol.Optional(CONF_DEVICE_CLASS): SENSOR_DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_ICON): str,
        vol.Optional(CONF_ENTITY_REGISTRY_ENABLED_DEFAULT): bool,
        vol.Optional(CONF_SUGGESTED_UNIT_OF_MEASUREMENT): str,
        vol.Optional(CONF_SUGGESTED_DISPLAY_PRECISION): int,
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

CONTROLLABLE_TEXT_SENSOR_SCHEMA = TEXT_SENSOR_SCHEMA.extend(
    {
        vol.Optional(CONF_MODE): vol.All(vol.Lower, vol.Coerce(TextMode)),
    }
)

NUMBER_SENSOR_SCHEMA = SENSOR_SCHEMA.extend(
    {
        vol.Optional(CONF_FLOAT): bool,
        vol.Optional(CONF_MINIMUM): vol.Coerce(float),
        vol.Optional(CONF_MAXIMUM): vol.Coerce(float),
    }
)

CONTROLLABLE_NUMBER_SENSOR_SCHEMA = NUMBER_SENSOR_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE_CLASS): NUMBER_DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_MODE): vol.All(vol.Lower, vol.Coerce(NumberMode)),
    }
)

BINARY_SENSOR_SCHEMA = SENSOR_SCHEMA.extend(
    {
        vol.Optional(CONF_COMMAND_ON): str,
        vol.Optional(CONF_COMMAND_OFF): str,
        vol.Optional(CONF_PAYLOAD_ON): str,
        vol.Optional(CONF_PAYLOAD_OFF): str,
        vol.Optional(CONF_DEVICE_CLASS): BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
    }
)

CONTROLLABLE_BINARY_SENSOR_SCHEMA = BINARY_SENSOR_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE_CLASS): SWITCH_DEVICE_CLASSES_SCHEMA,
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


class ListSelector(ObjectSelector):
    def __init__(
        self, schema: vol.Schema, config: Mapping[str, Any] | None = None
    ) -> None:
        super().__init__(config)
        self._schema = schema

    def __call__(self, data: Any) -> Any:
        return [self._schema(element) for element in data]


class OptionsFlow(config_entries.OptionsFlow):
    def __init_subclass__(cls, *, logger: logging.Logger = _LOGGER) -> None:
        super().__init_subclass__()
        cls.logger = logger

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry
        self._data = config_entry.options.copy()

    @property
    def init_schema(self) -> vol.Schema:
        return vol.Schema(
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
        )

    def validate_init(self, options: dict[str, Any]) -> dict[str, Any]:
        """Validate the options user input."""
        get_collection(self.hass, options)
        return options

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data = user_input
            try:
                options = self.validate_init(user_input)
            except ValueError:
                errors["base"] = "name_key_error"
            except Exception:  # pylint: disable=broad-except
                self.logger.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=self.init_schema,
        )


class ConfigFlow(config_entries.ConfigFlow):
    def __init_subclass__(
        cls,
        *,
        domain: str | None = None,
        logger: logging.Logger = _LOGGER,
        **kwargs: Any,
    ) -> None:
        super().__init_subclass__(domain=domain, **kwargs)
        cls.domain = domain
        cls.logger = logger

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

    @property
    def user_schema(self) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(
                    CONF_HOST,
                    default=self._data.get(CONF_HOST, vol.UNDEFINED),
                ): str,
                vol.Required(
                    CONF_PORT,
                    default=self._data.get(CONF_PORT, DEFAULT_PORT),
                ): int,
                vol.Optional(
                    CONF_USERNAME,
                    default=self._data.get(CONF_USERNAME, vol.UNDEFINED),
                ): str,
                vol.Optional(
                    CONF_PASSWORD,
                    default=self._data.get(CONF_PASSWORD, vol.UNDEFINED),
                ): str,
                vol.Required(
                    CONF_DEFAULT_COMMANDS,
                    default=self._data.get(CONF_DEFAULT_COMMANDS, vol.UNDEFINED),
                ): DEFAULT_COMMANDS_SELECTOR,
                vol.Optional(
                    CONF_KEY_FILENAME,
                    default=self._data.get(CONF_KEY_FILENAME, vol.UNDEFINED),
                ): str,
                vol.Optional(
                    CONF_HOST_KEYS_FILENAME,
                    default=self._data.get(
                        CONF_HOST_KEYS_FILENAME,
                        f"{self.hass.config.config_dir}/{DEFAULT_HOST_KEYS_FILENAME}",
                    ),
                ): str,
                vol.Required(
                    CONF_ADD_HOST_KEYS,
                    default=self._data.get(CONF_ADD_HOST_KEYS, DEFAULT_ADD_HOST_KEYS),
                ): bool,
            }
        )

    @property
    def mac_address_schema(self) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(
                    CONF_MAC, default=self._data.get(CONF_MAC, vol.UNDEFINED)
                ): str
            }
        )

    @property
    def name_schema(self) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(
                    CONF_NAME, default=self._data.get(CONF_NAME, vol.UNDEFINED)
                ): str
            }
        )

    async def async_validate_user(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate the config user input."""
        manager = SSHManager(
            data[CONF_HOST],
            add_host_keys=data[CONF_ADD_HOST_KEYS],
            port=data[CONF_PORT],
            username=data.get(CONF_USERNAME),
            password=data.get(CONF_PASSWORD),
            key_filename=data.get(CONF_KEY_FILENAME),
            host_keys_filename=data.get(CONF_HOST_KEYS_FILENAME),
            collection=(
                getattr(default_collections, key)
                if (key := data[CONF_DEFAULT_COMMANDS]) != "none"
                else None
            ),
            logger=self.logger,
        )

        await manager.async_update_state(raise_errors=True)
        await manager.async_disconnect()

        if mac_address := manager.mac_address:
            self.logger.debug("Detected MAC address: %s", mac_address)
            try:
                data[CONF_MAC] = self.validate_mac_address(mac_address)
            except MACAddressInvalidError as exc:
                self.logger.debug(exc)

        if hostname := manager.hostname:
            self.logger.debug("Detected hostname: %s", hostname)
            try:
                data[CONF_NAME] = await self.async_validate_name(hostname)
            except NameExistsError as exc:
                self.logger.debug(exc)

        options = {
            CONF_ALLOW_TURN_OFF: manager.allow_turn_off,
            CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
            CONF_COMMAND_TIMEOUT: manager.command_timeout,
            CONF_ACTION_COMMANDS: [
                get_action_command_config(command)
                for command in manager.action_commands
            ],
            CONF_SENSOR_COMMANDS: [
                get_sensor_command_config(command)
                for command in manager.sensor_commands
            ],
        }

        return data, options

    def validate_mac_address(self, mac_address: str) -> str:
        """Validate the mac address has the correct format."""
        mac_address = mac_address.strip().lower()

        pattern = (
            "^([0-9A-Fa-f]{2}[:-])"
            + "{5}([0-9A-Fa-f]{2})|"
            + "([0-9a-fA-F]{4}\\."
            + "[0-9a-fA-F]{4}\\."
            + "[0-9a-fA-F]{4})$"
        )

        if not re.fullmatch(pattern, mac_address):
            raise MACAddressInvalidError(f"MAC Address {mac_address} is invalid")

        return mac_address

    async def async_validate_name(self, name: str) -> str:
        """Validate the name doesn't exist yet."""
        name = name.strip()

        for entry in self.hass.config_entries.async_entries(self.domain):
            if slugify(entry.data[CONF_NAME]) == slugify(name):
                raise NameExistsError(f"Name {name} exists already")

        return name

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data = user_input
            try:
                self._data, self._options = await self.async_validate_user(user_input)
            except PermissionError as exc:
                errors["base"] = "permission_error"
                self.logger.warning(exc)
            except OfflineError as exc:
                errors["base"] = "offline_error"
                self.logger.warning(exc)
            except SSHHostKeyUnknownError as exc:
                self.logger.warning(exc)
                errors["base"] = "ssh_host_key_unknown_error"
            except SSHAuthenticationError as exc:
                self.logger.warning(exc)
                errors["base"] = "ssh_authentication_error"
            except SSHConnectError as exc:
                self.logger.warning(exc)
                errors["base"] = "ssh_connect_error"
            except Exception:  # pylint: disable=broad-except
                self.logger.exception("Unexpected exception")
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
            data_schema=self.user_schema,
        )

    async def async_step_mac_address(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the mac_address step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data[CONF_MAC] = user_input[CONF_MAC]
            try:
                self._data[CONF_MAC] = self.validate_mac_address(user_input[CONF_MAC])
            except MACAddressInvalidError as exc:
                self.logger.warning(exc)
                errors["base"] = "mac_address_invalid_error"
            except Exception:  # pylint: disable=broad-except
                self.logger.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                unique_id = format_mac(self._data[CONF_MAC])
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return await self.async_step_name()

        return self.async_show_form(
            step_id="mac_address",
            errors=errors,
            data_schema=self.mac_address_schema,
        )

    async def async_step_name(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the name step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data[CONF_NAME] = user_input[CONF_NAME]
            try:
                self._data[CONF_NAME] = await self.async_validate_name(
                    user_input[CONF_NAME]
                )
            except NameExistsError as exc:
                self.logger.warning(exc)
                errors["base"] = "name_exists_error"
            except Exception:  # pylint: disable=broad-except
                self.logger.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                title = self._data[CONF_NAME]
                return self.async_create_entry(
                    title=title, data=self._data, options=self._options
                )

        return self.async_show_form(
            step_id="name",
            errors=errors,
            data_schema=self.name_schema,
        )

    async def async_step_reauth(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Handle the reauth step."""
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
    """Error to indicate that the name already exists."""


class MACAddressInvalidError(Exception):
    """Error to indicate that the MAC address is invalid."""
