from __future__ import annotations

from collections.abc import Mapping
import logging
import re
from typing import Any

from ssh_terminal_manager import (
    DEFAULT_ADD_HOST_KEYS,
    DEFAULT_ALLOW_TURN_OFF,
    DEFAULT_COMMAND_TIMEOUT,
    DEFAULT_DISCONNECT_MODE,
    DEFAULT_INVOKE_SHELL,
    DEFAULT_LOAD_SYSTEM_HOST_KEYS,
    DEFAULT_PORT,
    AuthenticationError,
    Collection,
    CommandError,
    ConnectError,
    ExecutionError,
    HostKeyUnknownError,
    NameKeyError,
    OfflineError,
    SensorError,
    SSHManager,
    SSHTerminal,
    default_collections,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.button import (
    DEVICE_CLASSES_SCHEMA as BUTTON_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.number import (
    DEVICE_CLASSES_SCHEMA as NUMBER_DEVICE_CLASSES_SCHEMA,
    NumberMode,
)
from homeassistant.components.sensor import (
    DEVICE_CLASSES_SCHEMA as SENSOR_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.switch import (
    DEVICE_CLASSES_SCHEMA as SWITCH_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.text import TextMode
from homeassistant.components.update import (
    DEVICE_CLASSES_SCHEMA as UPDATE_DEVICE_CLASSES_SCHEMA,
)
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
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    BooleanSelector,
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
    CONF_DISCONNECT_MODE,
    CONF_DYNAMIC,
    CONF_ENTITY_REGISTRY_ENABLED_DEFAULT,
    CONF_FLOAT,
    CONF_HOST_KEYS_FILENAME,
    CONF_INVOKE_SHELL,
    CONF_KEY,
    CONF_KEY_FILENAME,
    CONF_LATEST,
    CONF_LOAD_SYSTEM_HOST_KEYS,
    CONF_OPTIONS,
    CONF_PATTERN,
    CONF_POWER_BUTTON,
    CONF_REMOVE_CUSTOM_COMMANDS,
    CONF_RESET_COMMANDS,
    CONF_RESET_DEFAULT_COMMANDS,
    CONF_SENSOR_COMMANDS,
    CONF_SENSORS,
    CONF_SEPARATOR,
    CONF_SUGGESTED_DISPLAY_PRECISION,
    CONF_SUGGESTED_UNIT_OF_MEASUREMENT,
    CONF_TIMEOUT_OFF,
    CONF_TIMEOUT_ON,
    CONF_TIMEOUT_SET,
    CONF_UPDATE_INTERVAL,
    DEFAULT_HOST_KEYS_FILENAME,
    DEFAULT_POWER_BUTTON,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .converter import Converter

_LOGGER = logging.getLogger(__name__)


def _sort_action_command(data: dict) -> dict:
    return {
        key: data[key]
        for key in [str(key) for key in ACTION_COMMAND_SCHEMA.schema]
        if key in data
    }


def _sort_sensor_command(data: dict) -> dict:
    return {
        key: (
            data[key]
            if key != CONF_SENSORS
            else [_sort_sensor(sensor) for sensor in data[key]]
        )
        for key in [str(key) for key in SENSOR_COMMAND_SCHEMA.schema]
        if key in data
    }


def _sort_sensor(data: dict) -> dict:
    return {
        key: data[key]
        for key in [str(key) for key in _get_sensor_schema(data).schema]
        if key in data
    }


def _get_sensor_schema(data: dict) -> vol.Schema:
    sensor_type = data[CONF_TYPE]
    controllable = (
        data.get(CONF_COMMAND_SET)
        or data.get(CONF_COMMAND_ON)
        and data.get(CONF_COMMAND_OFF)
    )

    if sensor_type == "text":
        if not controllable:
            return TEXT_SENSOR_SCHEMA
        return CONTROLLABLE_TEXT_SENSOR_SCHEMA

    if sensor_type == "number":
        if not controllable:
            return NUMBER_SENSOR_SCHEMA
        return CONTROLLABLE_NUMBER_SENSOR_SCHEMA

    if sensor_type == "binary":
        if not controllable:
            return BINARY_SENSOR_SCHEMA
        return CONTROLLABLE_BINARY_SENSOR_SCHEMA

    if sensor_type == "version":
        if not data.get(CONF_LATEST):
            return VERSION_SENSOR_SCHEMA
        return UPDATE_SCHEMA

    if sensor_type == "none":
        return SENSOR_SCHEMA

    raise ValueError("Invalid sensor type")


def _validate_sensor(data: dict) -> dict:
    return _get_sensor_schema(data)(data)


class ListSelector(ObjectSelector):
    def __init__(
        self, schema: vol.Schema, config: Mapping[str, Any] | None = None
    ) -> None:
        super().__init__(config)
        self._schema = schema

    def __call__(self, data: Any) -> Any:
        return [self._schema(element) for element in data]


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
        vol.Optional(CONF_SEPARATOR): str,
        vol.Required(CONF_SENSORS): vol.Schema([_validate_sensor]),
    }
)

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TYPE): vol.Any("text", "number", "binary", "version", "none"),
        vol.Optional(CONF_NAME): str,
        vol.Optional(CONF_KEY): str,
        vol.Optional(CONF_DYNAMIC): bool,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): str,
        vol.Optional(CONF_VALUE_TEMPLATE): str,
        vol.Optional(CONF_COMMAND_SET): str,
        vol.Optional(CONF_TIMEOUT_SET): int,
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
        vol.Optional(CONF_TIMEOUT_ON): int,
        vol.Optional(CONF_TIMEOUT_OFF): int,
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

VERSION_SENSOR_SCHEMA = SENSOR_SCHEMA

UPDATE_SCHEMA = VERSION_SENSOR_SCHEMA.extend(
    {
        vol.Required(CONF_LATEST): str,
        vol.Optional(CONF_DEVICE_CLASS): UPDATE_DEVICE_CLASSES_SCHEMA,
    }
)

CONFIG_FLOW_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT): int,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Required(CONF_DEFAULT_COMMANDS): DEFAULT_COMMANDS_SELECTOR,
        vol.Optional(CONF_KEY_FILENAME): str,
        vol.Optional(CONF_HOST_KEYS_FILENAME): str,
        vol.Required(CONF_ADD_HOST_KEYS): BooleanSelector(),
        vol.Required(CONF_LOAD_SYSTEM_HOST_KEYS): BooleanSelector(),
        vol.Required(CONF_INVOKE_SHELL): BooleanSelector(),
    }
)

CONFIG_FLOW_MAC_ADDRESS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC): str,
    }
)

CONFIG_FLOW_NAME_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
    }
)

OPTIONS_FLOW_INIT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ALLOW_TURN_OFF): BooleanSelector(),
        vol.Required(CONF_POWER_BUTTON): BooleanSelector(),
        vol.Required(CONF_DISCONNECT_MODE): BooleanSelector(),
        vol.Required(CONF_UPDATE_INTERVAL): int,
        vol.Required(CONF_COMMAND_TIMEOUT): int,
        vol.Required(CONF_ACTION_COMMANDS): ListSelector(ACTION_COMMAND_SCHEMA),
        vol.Required(CONF_SENSOR_COMMANDS): ListSelector(SENSOR_COMMAND_SCHEMA),
        vol.Required(CONF_RESET_COMMANDS): BooleanSelector(),
    }
)

OPTIONS_FLOW_RESET_COMMANDS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_RESET_DEFAULT_COMMANDS): BooleanSelector(),
        vol.Required(CONF_REMOVE_CUSTOM_COMMANDS): BooleanSelector(),
    }
)


class OptionsFlow(config_entries.OptionsFlow):
    """Handle a options flow for SSH."""

    logger = _LOGGER

    def __init__(self, config_entry: ConfigEntry) -> None:
        super().__init__()
        self._data = {**config_entry.options}
        self.sort_commands()

    @property
    def _default_collection(self) -> Collection | None:
        if (key := self.config_entry.data[CONF_DEFAULT_COMMANDS]) != "none":
            return getattr(default_collections, key)
        return None

    def validate_init(self, options: dict) -> dict[str, Any]:
        """Validate the options user input."""
        Converter(self.hass).get_collection(options)
        return options

    def sort_commands(self) -> None:
        """Sort the commands."""
        self._data = {
            **self._data,
            CONF_ACTION_COMMANDS: [
                _sort_action_command(command)
                for command in self._data[CONF_ACTION_COMMANDS]
            ],
            CONF_SENSOR_COMMANDS: [
                _sort_sensor_command(command)
                for command in self._data[CONF_SENSOR_COMMANDS]
            ],
        }

    def reset_commands(
        self, reset_default_commands: bool, remove_custom_commands: bool
    ) -> None:
        """Reset the commands."""
        if not reset_default_commands and not remove_custom_commands:
            return

        if self._default_collection:
            collection = Collection(
                "",
                self._default_collection.action_commands,
                self._default_collection.sensor_commands,
            )
        else:
            collection = Collection("")

        default_action_commands_by_key = collection.action_commands_by_key
        default_sensors_by_key = collection.sensors_by_key
        converter = Converter(self.hass)
        old_default_collection = converter.get_collection(self._data)
        old_custom_collection = converter.get_collection(self._data)

        for key in old_default_collection.action_commands_by_key:
            if key not in default_action_commands_by_key:
                old_default_collection.remove_action_command(key)

        for key in old_default_collection.sensors_by_key:
            if key not in default_sensors_by_key:
                old_default_collection.remove_sensor(key)

        for key in old_custom_collection.action_commands_by_key:
            if key in default_action_commands_by_key:
                old_custom_collection.remove_action_command(key)

        for key in old_custom_collection.sensors_by_key:
            if key in default_sensors_by_key:
                old_custom_collection.remove_sensor(key)

        if not reset_default_commands:
            collection = old_default_collection

        if not remove_custom_commands:
            for command in old_custom_collection.action_commands:
                collection.add_action_command(command)

            for command in old_custom_collection.sensor_commands:
                collection.add_sensor_command(command)

        collection.check()

        self._data = {
            **self._data,
            CONF_ACTION_COMMANDS: [
                converter.get_action_command_config(command)
                for command in collection.action_commands
            ],
            CONF_SENSOR_COMMANDS: [
                converter.get_sensor_command_config(command)
                for command in collection.sensor_commands
            ],
        }

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            reset_commands = user_input.pop(CONF_RESET_COMMANDS)
            self._data = user_input
            try:
                self._data = self.validate_init(user_input)
            except NameKeyError:
                errors["base"] = "name_key_error"
            except CommandError as exc:
                errors["base"] = "command_error"
                placeholders["details"] = f"({exc.details})" if exc.details else ""
            except SensorError as exc:
                errors["base"] = "sensor_error"
                placeholders["key"] = exc.key
                placeholders["details"] = f"({exc.details})" if exc.details else ""
            except Exception:
                self.logger.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if reset_commands:
                    return await self.async_step_reset_commands()
                return self.async_create_entry(title="", data=self._data)

        return self.async_show_form(
            step_id="init",
            errors=errors,
            description_placeholders=placeholders,
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_FLOW_INIT_SCHEMA,
                {
                    **self._data,
                    CONF_RESET_COMMANDS: False,
                },
            ),
        )

    async def async_step_reset_commands(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the reset commands step."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            try:
                self.reset_commands(
                    user_input[CONF_RESET_DEFAULT_COMMANDS],
                    user_input[CONF_REMOVE_CUSTOM_COMMANDS],
                )
            except CommandError as exc:
                errors["base"] = "command_error"
                placeholders["details"] = f"({exc.details})" if exc.details else ""
            except SensorError as exc:
                errors["base"] = "sensor_error"
                placeholders["key"] = exc.key
                placeholders["details"] = f"({exc.details})" if exc.details else ""
            except Exception:
                self.logger.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="", data=self._data)

        return self.async_show_form(
            step_id="reset_commands",
            errors=errors,
            description_placeholders=placeholders,
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_FLOW_RESET_COMMANDS_SCHEMA,
                {
                    CONF_RESET_DEFAULT_COMMANDS: True,
                    CONF_REMOVE_CUSTOM_COMMANDS: False,
                },
            ),
        )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SSH."""

    VERSION = 2
    MINOR_VERSION = 2
    logger = _LOGGER
    domain = DOMAIN
    _existing_entry: ConfigEntry | None = None
    _data: dict[str, Any]
    _options: dict[str, Any]

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlow(config_entry)

    def __init__(self) -> None:
        super().__init__()
        self._data = {}
        self._options = {}

    def get_mac_address(self, manager: SSHManager) -> str | None:
        """Get MAC address from manager."""
        if mac_address := manager.mac_address:
            self.logger.debug("Detected MAC address: %s", mac_address)
            try:
                return self.validate_mac_address(mac_address)
            except MACAddressInvalidError as exc:
                self.logger.debug(exc)

        return None

    async def async_get_hostname(self, manager: SSHManager) -> str | None:
        """Get hostname from manager."""
        if hostname := manager.hostname:
            self.logger.debug("Detected hostname: %s", hostname)
            try:
                return await self.async_validate_name(hostname)
            except NameExistsError as exc:
                self.logger.debug(exc)

        return None

    def get_options(self, manager: SSHManager) -> dict:
        """Get options from manager."""
        converter = Converter(self.hass)
        return {
            CONF_ALLOW_TURN_OFF: DEFAULT_ALLOW_TURN_OFF,
            CONF_POWER_BUTTON: DEFAULT_POWER_BUTTON,
            CONF_DISCONNECT_MODE: DEFAULT_DISCONNECT_MODE,
            CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
            CONF_COMMAND_TIMEOUT: DEFAULT_COMMAND_TIMEOUT,
            CONF_ACTION_COMMANDS: [
                converter.get_action_command_config(command)
                for command in manager.action_commands
            ],
            CONF_SENSOR_COMMANDS: [
                converter.get_sensor_command_config(command)
                for command in manager.sensor_commands
            ],
        }

    async def async_validate_user(self, data: dict) -> tuple[dict, dict]:
        """Validate the config user input."""
        terminal = SSHTerminal(
            data[CONF_HOST],
            port=data[CONF_PORT],
            username=data.get(CONF_USERNAME),
            password=data.get(CONF_PASSWORD),
            key_filename=data.get(CONF_KEY_FILENAME),
            host_keys_filename=data.get(CONF_HOST_KEYS_FILENAME),
            add_host_keys=data[CONF_ADD_HOST_KEYS],
            load_system_host_keys=data[CONF_LOAD_SYSTEM_HOST_KEYS],
            invoke_shell=data[CONF_INVOKE_SHELL],
        )

        manager = SSHManager(
            terminal,
            collection=(
                getattr(default_collections, key)
                if (key := data[CONF_DEFAULT_COMMANDS]) != "none"
                else None
            ),
            logger=self.logger,
        )

        await manager.async_load_host_keys()

        async with manager:
            await manager.async_update()

        data = {
            **data,
            CONF_MAC: self.get_mac_address(manager),
            CONF_NAME: await self.async_get_hostname(manager),
        }
        options = self.get_options(manager)

        return data, options

    def validate_mac_address(self, mac_address: str) -> str:
        """Validate the mac address has the correct format."""
        mac_address = mac_address.strip().lower()
        pattern = (
            "^([0-9A-Fa-f]{2}[:-])"
            "{5}([0-9A-Fa-f]{2})|"
            "([0-9a-fA-F]{4}\\."
            "[0-9a-fA-F]{4}\\."
            "[0-9a-fA-F]{4})$"
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

    async def async_handle_step_user_success(self) -> FlowResult:
        """Continue with step mac address or update existing entry."""
        if not self._existing_entry:
            return await self.async_step_mac_address()

        return self.async_update_reload_and_abort(
            self._existing_entry,
            data={
                **self._data,
                CONF_MAC: self._existing_entry.data[CONF_MAC],
                CONF_NAME: self._existing_entry.data[CONF_NAME],
            },
            reason=(
                "reauth_successful"
                if self.source == config_entries.SOURCE_REAUTH
                else "reconf_successful"
            ),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            self._data = user_input
            try:
                self._data, self._options = await self.async_validate_user(user_input)
            except PermissionError:
                errors["base"] = "permission_error"
            except OfflineError as exc:
                errors["base"] = "offline_error"
                placeholders["host"] = exc.host
            except HostKeyUnknownError as exc:
                errors["base"] = "host_key_unknown_error"
                placeholders["host"] = exc.host
            except AuthenticationError as exc:
                errors["base"] = "authentication_error"
                placeholders["details"] = f"({exc.details})" if exc.details else ""
            except ConnectError as exc:
                errors["base"] = "connect_error"
                placeholders["details"] = f"({exc.details})" if exc.details else ""
            except ExecutionError as exc:
                errors["base"] = "execution_error"
                placeholders["details"] = f"({exc.details})" if exc.details else ""
            except Exception:
                self.logger.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return await self.async_handle_step_user_success()

        return self.async_show_form(
            step_id="user",
            errors=errors,
            description_placeholders=placeholders,
            data_schema=self.add_suggested_values_to_schema(
                CONFIG_FLOW_USER_SCHEMA,
                {
                    **self._data,
                    CONF_PORT: self._data.get(CONF_PORT, DEFAULT_PORT),
                    CONF_HOST_KEYS_FILENAME: self._data.get(
                        CONF_HOST_KEYS_FILENAME,
                        f"{self.hass.config.config_dir}/{DEFAULT_HOST_KEYS_FILENAME}",
                    ),
                    CONF_ADD_HOST_KEYS: self._data.get(
                        CONF_ADD_HOST_KEYS, DEFAULT_ADD_HOST_KEYS
                    ),
                    CONF_LOAD_SYSTEM_HOST_KEYS: self._data.get(
                        CONF_LOAD_SYSTEM_HOST_KEYS, DEFAULT_LOAD_SYSTEM_HOST_KEYS
                    ),
                    CONF_INVOKE_SHELL: self._data.get(
                        CONF_INVOKE_SHELL, DEFAULT_INVOKE_SHELL
                    ),
                },
            ),
        )

    async def async_step_mac_address(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the mac_address step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data[CONF_MAC] = (mac_address := user_input[CONF_MAC])
            try:
                self._data[CONF_MAC] = self.validate_mac_address(mac_address)
            except MACAddressInvalidError:
                errors["base"] = "mac_address_invalid_error"
            except Exception:
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
            data_schema=self.add_suggested_values_to_schema(
                CONFIG_FLOW_MAC_ADDRESS_SCHEMA,
                self._data,
            ),
        )

    async def async_step_name(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the name step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data[CONF_NAME] = (name := user_input[CONF_NAME])
            try:
                self._data[CONF_NAME] = await self.async_validate_name(name)
            except NameExistsError:
                errors["base"] = "name_exists_error"
            except Exception:
                self.logger.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=self._data[CONF_NAME],
                    data=self._data,
                    options=self._options,
                )

        return self.async_show_form(
            step_id="name",
            errors=errors,
            data_schema=self.add_suggested_values_to_schema(
                CONFIG_FLOW_NAME_SCHEMA,
                self._data,
            ),
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        """Handle the reconfigure step."""
        self._existing_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        self._data = {**self._existing_entry.data}
        return await self.async_step_user()

    async def async_step_reauth(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Handle the reauth step."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_reconfigure()


class NameExistsError(Exception):
    """Error to indicate that the name already exists."""


class MACAddressInvalidError(Exception):
    """Error to indicate that the MAC address is invalid."""
