from __future__ import annotations

from collections.abc import Callable

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
    CONF_OPTIONS,
    CONF_PATTERN,
    CONF_SENSOR_COMMANDS,
    CONF_SENSORS,
    CONF_SEPARATOR,
    CONF_SUGGESTED_DISPLAY_PRECISION,
    CONF_SUGGESTED_UNIT_OF_MEASUREMENT,
)
from .helpers import get_command_renderer, get_value_renderer

ACTION_ATTRIBUTE_KEYS = (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_ENTITY_REGISTRY_ENABLED_DEFAULT,
)

SENSOR_ATTRIBUTE_KEYS = (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_ENTITY_REGISTRY_ENABLED_DEFAULT,
    CONF_SUGGESTED_UNIT_OF_MEASUREMENT,
    CONF_SUGGESTED_DISPLAY_PRECISION,
    CONF_MODE,
)

DEFAULT_ACTION_ATTRIBUTES: dict[str, dict] = {
    ActionKey.RESTART: {CONF_DEVICE_CLASS: ButtonDeviceClass.RESTART},
}

DEFAULT_SENSOR_ATTRIBUTES: dict[str, dict] = {
    SensorKey.NETWORK_INTERFACE: {CONF_ICON: "mdi:wan"},
    SensorKey.MAC_ADDRESS: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.WAKE_ON_LAN: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.MACHINE_TYPE: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.HOSTNAME: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.OS_NAME: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.OS_VERSION: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
    SensorKey.OS_ARCHITECTURE: {CONF_ENTITY_REGISTRY_ENABLED_DEFAULT: False},
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


def value_renderer_or_none(hass: HomeAssistant, string: str | None) -> Callable | None:
    return get_value_renderer(hass, string) if string else None


def command_or_none(hass: HomeAssistant, string: str | None) -> Command | None:
    return Command(string, renderer=get_command_renderer(hass)) if string else None


def get_sensor_config(sensor: Sensor) -> dict:
    return remove_none_items(
        {
            CONF_NAME: sensor.name,
            CONF_KEY: sensor.key,
            CONF_DYNAMIC: sensor.dynamic is True or None,
            CONF_SEPARATOR: sensor.separator,
            CONF_UNIT_OF_MEASUREMENT: sensor.unit,
            CONF_COMMAND_SET: sensor.command_set.string if sensor.command_set else None,
        }
    )


def get_sensor_kwargs(hass: HomeAssistant, data: dict) -> dict:
    return {
        "name": data.get(CONF_NAME),
        "key": data.get(CONF_KEY),
        "dynamic": data.get(CONF_DYNAMIC, False),
        "separator": data.get(CONF_SEPARATOR),
        "unit": data.get(CONF_UNIT_OF_MEASUREMENT),
        "renderer": value_renderer_or_none(hass, data.get(CONF_VALUE_TEMPLATE)),
        "command_set": command_or_none(hass, data.get(CONF_COMMAND_SET)),
        "attributes": {
            **DEFAULT_SENSOR_ATTRIBUTES.get(data.get(CONF_KEY), {}),
            **{key: data[key] for key in SENSOR_ATTRIBUTE_KEYS if key in data},
        },
    }


def get_text_sensor_config(sensor: TextSensor) -> dict:
    return remove_none_items(
        {
            CONF_TYPE: "text",
            **get_sensor_config(sensor),
            CONF_MINIMUM: sensor.minimum,
            CONF_MAXIMUM: sensor.maximum,
            CONF_PATTERN: sensor.pattern,
            CONF_OPTIONS: sensor.options,
        }
    )


def get_text_sensor_kwargs(hass: HomeAssistant, data: dict) -> dict:
    return {
        **get_sensor_kwargs(hass, data),
        "minimum": data.get(CONF_MINIMUM),
        "maximum": data.get(CONF_MAXIMUM),
        "pattern": data.get(CONF_PATTERN),
        "options": data.get(CONF_OPTIONS),
    }


def get_number_sensor_config(sensor: NumberSensor) -> dict:
    return remove_none_items(
        {
            CONF_TYPE: "number",
            **get_sensor_config(sensor),
            CONF_FLOAT: sensor.float is True or None,
            CONF_MINIMUM: sensor.minimum,
            CONF_MAXIMUM: sensor.maximum,
        }
    )


def get_number_sensor_kwargs(hass: HomeAssistant, data: dict) -> dict:
    return {
        **get_sensor_kwargs(hass, data),
        "float": data.get(CONF_FLOAT, False),
        "minimum": data.get(CONF_MINIMUM),
        "maximum": data.get(CONF_MAXIMUM),
    }


def get_binary_sensor_config(sensor: BinarySensor) -> dict:
    return remove_none_items(
        {
            CONF_TYPE: "binary",
            **get_sensor_config(sensor),
            CONF_COMMAND_ON: sensor.command_on.string if sensor.command_on else None,
            CONF_COMMAND_OFF: sensor.command_off.string if sensor.command_off else None,
            CONF_PAYLOAD_ON: sensor.payload_on,
            CONF_PAYLOAD_OFF: sensor.payload_off,
        }
    )


def get_binary_sensor_kwargs(hass: HomeAssistant, data: dict) -> dict:
    return {
        **get_sensor_kwargs(hass, data),
        "command_on": command_or_none(hass, data.get(CONF_COMMAND_ON)),
        "command_off": command_or_none(hass, data.get(CONF_COMMAND_OFF)),
        "payload_on": data.get(CONF_PAYLOAD_ON),
        "payload_off": data.get(CONF_PAYLOAD_OFF),
    }


def get_command_config(command: Command) -> dict:
    return remove_none_items(
        {
            CONF_COMMAND: command.string,
            CONF_TIMEOUT: command.timeout,
        }
    )


def get_command_kwargs(hass: HomeAssistant, data: dict) -> dict:
    return {
        "string": data[CONF_COMMAND],
        "timeout": data.get(CONF_TIMEOUT),
        "renderer": get_command_renderer(hass),
    }


def get_action_command_config(command: ActionCommand) -> dict:
    return remove_none_items(
        {
            **get_command_config(command),
            CONF_NAME: command.name,
            CONF_KEY: command.key,
        }
    )


def get_action_command_kwargs(hass: HomeAssistant, data: dict) -> dict:
    return {
        **get_command_kwargs(hass, data),
        "name": data.get(CONF_NAME),
        "key": data.get(CONF_KEY),
        "attributes": {
            **DEFAULT_ACTION_ATTRIBUTES.get(data.get(CONF_KEY), {}),
            **{key: data[key] for key in ACTION_ATTRIBUTE_KEYS if key in data},
        },
    }


def get_sensor_command_config(command: SensorCommand) -> dict:
    return remove_none_items(
        {
            **get_command_config(command),
            CONF_SCAN_INTERVAL: command.interval,
            CONF_SENSORS: [
                get_text_sensor_config(sensor)
                if isinstance(sensor, TextSensor)
                else get_number_sensor_config(sensor)
                if isinstance(sensor, NumberSensor)
                else get_binary_sensor_config(sensor)
                if isinstance(sensor, BinarySensor)
                else {CONF_TYPE: "placeholder"}
                for sensor in command.sensors
            ],
        }
    )


def get_sensor_command_kwargs(hass: HomeAssistant, data: dict) -> dict:
    return {
        **get_command_kwargs(hass, data),
        "interval": data.get(CONF_SCAN_INTERVAL),
        "sensors": [
            TextSensor(**get_text_sensor_kwargs(hass, sensor_data))
            if sensor_data[CONF_TYPE] == "text"
            else NumberSensor(**get_number_sensor_kwargs(hass, sensor_data))
            if sensor_data[CONF_TYPE] == "number"
            else BinarySensor(**get_binary_sensor_kwargs(hass, sensor_data))
            if sensor_data[CONF_TYPE] == "binary"
            else Sensor(key=PLACEHOLDER_KEY)
            for sensor_data in data[CONF_SENSORS]
        ],
    }


def get_collection(hass: HomeAssistant, options: dict) -> Collection:
    return Collection(
        "",
        [
            ActionCommand(**get_action_command_kwargs(hass, command_data))
            for command_data in options[CONF_ACTION_COMMANDS]
        ],
        [
            SensorCommand(**get_sensor_command_kwargs(hass, command_data))
            for command_data in options[CONF_SENSOR_COMMANDS]
        ],
    )
