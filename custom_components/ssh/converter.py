from __future__ import annotations

from ssh_terminal_manager import (
    PLACEHOLDER_KEY,
    ActionCommand,
    ActionKey,
    BinarySensor,
    Collection,
    Command,
    NumberSensor,
    Sensor,
    SensorCommand,
    SensorKey,
    TextSensor,
    VersionSensor,
)

from homeassistant.components.button import ButtonDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    CONF_COMMAND,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_DEVICE_CLASS,
    CONF_ICON,
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
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ACTION_COMMANDS,
    CONF_COMMAND_SET,
    CONF_DYNAMIC,
    CONF_ENTITY_REGISTRY_ENABLED_DEFAULT,
    CONF_FLOAT,
    CONF_KEY,
    CONF_LATEST,
    CONF_OPTIONS,
    CONF_PATTERN,
    CONF_SENSOR_COMMANDS,
    CONF_SENSORS,
    CONF_SEPARATOR,
    CONF_SUGGESTED_DISPLAY_PRECISION,
    CONF_SUGGESTED_UNIT_OF_MEASUREMENT,
    CONF_TIMEOUT_OFF,
    CONF_TIMEOUT_ON,
    CONF_TIMEOUT_SET,
)
from .helpers import get_command_renderer, get_value_renderer

ACTION_ATTR_KEYS = (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_ENTITY_REGISTRY_ENABLED_DEFAULT,
)

SENSOR_ATTR_KEYS = (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_ENTITY_REGISTRY_ENABLED_DEFAULT,
    CONF_SUGGESTED_UNIT_OF_MEASUREMENT,
    CONF_SUGGESTED_DISPLAY_PRECISION,
    CONF_MODE,
)

ACTION_ATTR_DEFAULTS: dict[str, dict] = {
    ActionKey.RESTART: {CONF_DEVICE_CLASS: ButtonDeviceClass.RESTART},
}

SENSOR_ATTR_DEFAULTS: dict[str, dict] = {
    SensorKey.NETWORK_INTERFACE: {CONF_ICON: "mdi:wan"},
    SensorKey.MAC_ADDRESS: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.WAKE_ON_LAN: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.MACHINE_TYPE: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.HOSTNAME: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.OS_NAME: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.OS_VERSION: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.OS_RELEASE: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.OS_ARCHITECTURE: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.DEVICE_NAME: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.DEVICE_MODEL: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.MANUFACTURER: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.SERIAL_NUMBER: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.CPU_NAME: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.CPU_CORES: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.CPU_HARDWARE: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.CPU_MODEL: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.TOTAL_MEMORY: {
        CONF_SUGGESTED_UNIT_OF_MEASUREMENT: "MB",
        CONF_SUGGESTED_DISPLAY_PRECISION: 0,
        CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
        CONF_ICON: "mdi:memory",
        CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False,
    },
    SensorKey.FREE_MEMORY: {
        CONF_SUGGESTED_UNIT_OF_MEASUREMENT: "MB",
        CONF_SUGGESTED_DISPLAY_PRECISION: 0,
        CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
        CONF_ICON: "mdi:memory",
    },
    SensorKey.FREE_DISK_SPACE: {
        CONF_SUGGESTED_UNIT_OF_MEASUREMENT: "MB",
        CONF_SUGGESTED_DISPLAY_PRECISION: 0,
        CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
        CONF_ICON: "mdi:harddisk",
    },
    SensorKey.TEMPERATURE: {CONF_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE},
    SensorKey.CPU_LOAD: {CONF_ICON: "mdi:server"},
    SensorKey.PROCESSES: {CONF_ICON: "mdi:cogs"},
}


def remove_none_items(data: dict) -> dict:
    return {key: value for key, value in data.items() if value is not None}


class Converter:
    def __init__(
        self,
        hass: HomeAssistant,
        action_attr_defaults: dict[str, dict] | None = None,
        sensor_attr_defaults: dict[str, dict] | None = None,
    ) -> None:
        self._hass = hass
        self._action_attr_defaults = action_attr_defaults or ACTION_ATTR_DEFAULTS
        self._sensor_attr_defaults = sensor_attr_defaults or SENSOR_ATTR_DEFAULTS

    def _get_sensor_config(self, sensor: Sensor) -> dict:
        return remove_none_items(
            {
                CONF_NAME: sensor.name,
                CONF_KEY: sensor.key,
                CONF_DYNAMIC: sensor.dynamic is True or None,
                CONF_UNIT_OF_MEASUREMENT: sensor.unit,
                CONF_COMMAND_SET: sensor.command_set.string
                if sensor.command_set
                else None,
                CONF_TIMEOUT_SET: sensor.command_set.timeout
                if sensor.command_set
                else None,
            }
        )

    def _get_sensor_kwargs(self, data: dict) -> dict:
        return {
            "name": data.get(CONF_NAME),
            "key": data.get(CONF_KEY),
            "dynamic": data.get(CONF_DYNAMIC, False),
            "unit": data.get(CONF_UNIT_OF_MEASUREMENT),
            "renderer": get_value_renderer(self._hass, value_template)
            if (value_template := data.get(CONF_VALUE_TEMPLATE))
            else None,
            "command_set": Command(
                string,
                timeout=data.get(CONF_TIMEOUT_SET),
                renderer=get_command_renderer(self._hass),
            )
            if (string := data.get(CONF_COMMAND_SET))
            else None,
            "attributes": {
                **self._sensor_attr_defaults.get(data.get(CONF_KEY), {}),
                **{key: data[key] for key in SENSOR_ATTR_KEYS if key in data},
            },
        }

    def _get_text_sensor_config(self, sensor: TextSensor) -> dict:
        return remove_none_items(
            {
                CONF_TYPE: "text",
                **self._get_sensor_config(sensor),
                CONF_MINIMUM: sensor.minimum,
                CONF_MAXIMUM: sensor.maximum,
                CONF_PATTERN: sensor.pattern,
                CONF_OPTIONS: sensor.options,
            }
        )

    def _get_text_sensor_kwargs(self, data: dict) -> dict:
        return {
            **self._get_sensor_kwargs(data),
            "minimum": data.get(CONF_MINIMUM),
            "maximum": data.get(CONF_MAXIMUM),
            "pattern": data.get(CONF_PATTERN),
            "options": data.get(CONF_OPTIONS),
        }

    def _get_number_sensor_config(self, sensor: NumberSensor) -> dict:
        return remove_none_items(
            {
                CONF_TYPE: "number",
                **self._get_sensor_config(sensor),
                CONF_FLOAT: sensor.float is True or None,
                CONF_MINIMUM: sensor.minimum,
                CONF_MAXIMUM: sensor.maximum,
            }
        )

    def _get_number_sensor_kwargs(self, data: dict) -> dict:
        return {
            **self._get_sensor_kwargs(data),
            "float": data.get(CONF_FLOAT, False),
            "minimum": data.get(CONF_MINIMUM),
            "maximum": data.get(CONF_MAXIMUM),
        }

    def _get_binary_sensor_config(self, sensor: BinarySensor) -> dict:
        return remove_none_items(
            {
                CONF_TYPE: "binary",
                **self._get_sensor_config(sensor),
                CONF_COMMAND_ON: sensor.command_on.string
                if sensor.command_on
                else None,
                CONF_COMMAND_OFF: sensor.command_off.string
                if sensor.command_off
                else None,
                CONF_TIMEOUT_ON: sensor.command_on.timeout
                if sensor.command_on
                else None,
                CONF_TIMEOUT_OFF: sensor.command_off.timeout
                if sensor.command_off
                else None,
                CONF_PAYLOAD_ON: sensor.payload_on,
                CONF_PAYLOAD_OFF: sensor.payload_off,
            }
        )

    def _get_binary_sensor_kwargs(self, data: dict) -> dict:
        return {
            **self._get_sensor_kwargs(data),
            "command_on": Command(
                string,
                timeout=data.get(CONF_TIMEOUT_ON),
                renderer=get_command_renderer(self._hass),
            )
            if (string := data.get(CONF_COMMAND_ON))
            else None,
            "command_off": Command(
                string,
                timeout=data.get(CONF_TIMEOUT_OFF),
                renderer=get_command_renderer(self._hass),
            )
            if (string := data.get(CONF_COMMAND_OFF))
            else None,
            "payload_on": data.get(CONF_PAYLOAD_ON),
            "payload_off": data.get(CONF_PAYLOAD_OFF),
        }

    def _get_version_sensor_config(self, sensor: VersionSensor) -> dict:
        return remove_none_items(
            {
                CONF_TYPE: "version",
                **self._get_sensor_config(sensor),
                CONF_LATEST: sensor.latest,
            }
        )

    def _get_version_sensor_kwargs(self, data: dict) -> dict:
        return {
            **self._get_sensor_kwargs(data),
            "latest": data.get(CONF_LATEST),
        }

    def _get_command_config(self, command: Command) -> dict:
        return remove_none_items(
            {
                CONF_COMMAND: command.string,
                CONF_TIMEOUT: command.timeout,
            }
        )

    def _get_command_kwargs(self, data: dict) -> dict:
        return {
            "string": data[CONF_COMMAND],
            "timeout": data.get(CONF_TIMEOUT),
            "renderer": get_command_renderer(self._hass),
        }

    def get_action_command_config(self, command: ActionCommand) -> dict:
        """Get the action command config."""
        return remove_none_items(
            {
                **self._get_command_config(command),
                CONF_NAME: command.name,
                CONF_KEY: command.key,
            }
        )

    def get_action_command_kwargs(self, data: dict) -> dict:
        """Get the action command kwargs."""
        return {
            **self._get_command_kwargs(data),
            "name": data.get(CONF_NAME),
            "key": data.get(CONF_KEY),
            "attributes": {
                **self._action_attr_defaults.get(data.get(CONF_KEY), {}),
                **{key: data[key] for key in ACTION_ATTR_KEYS if key in data},
            },
        }

    def get_sensor_command_config(self, command: SensorCommand) -> dict:
        """Get the sensor command config."""
        return remove_none_items(
            {
                **self._get_command_config(command),
                CONF_SCAN_INTERVAL: command.interval,
                CONF_SEPARATOR: command.separator,
                CONF_SENSORS: [
                    self._get_text_sensor_config(sensor)
                    if isinstance(sensor, TextSensor)
                    else self._get_number_sensor_config(sensor)
                    if isinstance(sensor, NumberSensor)
                    else self._get_binary_sensor_config(sensor)
                    if isinstance(sensor, BinarySensor)
                    else self._get_version_sensor_config(sensor)
                    if isinstance(sensor, VersionSensor)
                    else {CONF_TYPE: "none"}
                    for sensor in command.sensors
                ],
            }
        )

    def get_sensor_command_kwargs(self, data: dict) -> dict:
        """Get the sensor command kwargs."""
        return {
            **self._get_command_kwargs(data),
            "interval": data.get(CONF_SCAN_INTERVAL),
            "separator": data.get(CONF_SEPARATOR),
            "sensors": [
                TextSensor(**self._get_text_sensor_kwargs(sensor_data))
                if sensor_data[CONF_TYPE] == "text"
                else NumberSensor(**self._get_number_sensor_kwargs(sensor_data))
                if sensor_data[CONF_TYPE] == "number"
                else BinarySensor(**self._get_binary_sensor_kwargs(sensor_data))
                if sensor_data[CONF_TYPE] == "binary"
                else VersionSensor(**self._get_version_sensor_kwargs(sensor_data))
                if sensor_data[CONF_TYPE] == "version"
                else Sensor(key=PLACEHOLDER_KEY)
                for sensor_data in data[CONF_SENSORS]
            ],
        }

    def get_collection(self, options: dict) -> Collection:
        """Get the collection."""
        return Collection(
            "",
            [
                ActionCommand(**self.get_action_command_kwargs(command_data))
                for command_data in options[CONF_ACTION_COMMANDS]
            ],
            [
                SensorCommand(**self.get_sensor_command_kwargs(command_data))
                for command_data in options[CONF_SENSOR_COMMANDS]
            ],
        )
