from __future__ import annotations

from ssh_remote_control import (
    ActionCommand,
    ActionKey,
    Command,
    CommandSet,
    DynamicSensor,
    Remote,
    Sensor,
    SensorCommand,
    SensorKey,
)

from homeassistant.components.button import ButtonDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    CONF_COMMAND,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_DEVICE_CLASS,
    CONF_ENABLED,
    CONF_ICON,
    CONF_NAME,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ACTION_COMMANDS,
    CONF_COMMAND_SET,
    CONF_DYNAMIC,
    CONF_KEY,
    CONF_SENSOR_COMMANDS,
    CONF_SENSORS,
    CONF_SEPARATOR,
    CONF_SUGGESTED_UNIT_OF_MEASUREMENT,
    CONF_VALUE_MAX,
    CONF_VALUE_MIN,
    CONF_VALUE_TYPE,
)
from .helpers import get_command_renderer, get_value_renderer

DEFAULT_ACTION_OPTIONS: dict[str, dict] = {
    ActionKey.RESTART: {CONF_DEVICE_CLASS: ButtonDeviceClass.RESTART},
}

DEFAULT_SENSOR_OPTIONS: dict[str, dict] = {
    SensorKey.MAC_ADDRESS: {CONF_ENABLED: False},
    SensorKey.WOL_SUPPORT: {CONF_ENABLED: False},
    SensorKey.INTERFACE: {CONF_ENABLED: False},
    SensorKey.MACHINE_TYPE: {CONF_ENABLED: False},
    SensorKey.HOSTNAME: {CONF_ENABLED: False},
    SensorKey.OS_NAME: {CONF_ENABLED: False},
    SensorKey.OS_VERSION: {CONF_ENABLED: False},
    SensorKey.TOTAL_MEMORY: {
        CONF_ICON: "mdi:memory",
        CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
        CONF_SUGGESTED_UNIT_OF_MEASUREMENT: "GB",
        CONF_ENABLED: False,
    },
    SensorKey.FREE_MEMORY: {
        CONF_ICON: "mdi:memory",
        CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
        CONF_SUGGESTED_UNIT_OF_MEASUREMENT: "GB",
    },
    SensorKey.FREE_DISK_SPACE: {
        CONF_ICON: "mdi:harddisk",
        CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
        CONF_SUGGESTED_UNIT_OF_MEASUREMENT: "GB",
    },
    SensorKey.TEMPERATURE: {
        CONF_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
    },
    SensorKey.CPU_LOAD: {CONF_ICON: "mdi:server"},
}

SENSOR_OPTIONS_KEYS = (
    CONF_SUGGESTED_UNIT_OF_MEASUREMENT,
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_ENABLED,
)

ACTION_OPTIONS_KEYS = (CONF_DEVICE_CLASS, CONF_ICON, CONF_ENABLED)


def _remove_none_items(data: dict) -> dict:
    return {key: value for key, value in data.items() if value is not None}


def _value_type_to_string(value_type: type) -> str:
    return {int: "int", float: "float", bool: "bool"}.get(value_type)


def _string_to_value_type(string: str) -> type:
    return {"int": int, "float": float, "bool": bool}.get(string)


def _action_command_to_conf(command: ActionCommand) -> dict:
    return _remove_none_items(
        {
            CONF_COMMAND: command.string,
            CONF_NAME: command.name,
            CONF_KEY: command.key,
            CONF_TIMEOUT: command.timeout,
        }
    )


def _conf_to_action_command(hass: HomeAssistant, data: dict) -> ActionCommand:
    options = DEFAULT_ACTION_OPTIONS.get(data.get(CONF_KEY), {})

    for key in ACTION_OPTIONS_KEYS:
        if key in data:
            options[key] = data[key]

    return ActionCommand(
        data[CONF_COMMAND],
        data.get(CONF_NAME),
        data.get(CONF_KEY),
        timeout=data.get(CONF_TIMEOUT),
        renderer=get_command_renderer(hass),
        options=options,
    )


def _sensor_to_conf(sensor: Sensor) -> dict:
    return _remove_none_items(
        {
            CONF_NAME: sensor.name,
            CONF_KEY: sensor.key,
            CONF_DYNAMIC: isinstance(sensor, DynamicSensor) or None,
            CONF_SEPARATOR: sensor.separator
            if isinstance(sensor, DynamicSensor)
            else None,
            CONF_VALUE_TYPE: _value_type_to_string(sensor.value_type),
            CONF_VALUE_MIN: sensor.value_min,
            CONF_VALUE_MAX: sensor.value_max,
            CONF_UNIT_OF_MEASUREMENT: sensor.value_unit,
            CONF_COMMAND_SET: sensor.command_set,
            CONF_COMMAND_ON: sensor.command_on.string if sensor.command_on else None,
            CONF_COMMAND_OFF: sensor.command_off.string if sensor.command_off else None,
            CONF_PAYLOAD_ON: sensor.payload_on,
            CONF_PAYLOAD_OFF: sensor.payload_off,
        }
    )


def _conf_to_sensor(hass: HomeAssistant, data: dict) -> Sensor | DynamicSensor:
    options = DEFAULT_SENSOR_OPTIONS.get(data.get(CONF_KEY), {})

    for key in SENSOR_OPTIONS_KEYS:
        if key in data:
            options[key] = data[key]

    sensor = (DynamicSensor if data.get(CONF_DYNAMIC) else Sensor)(
        data.get(CONF_NAME),
        data.get(CONF_KEY),
        value_type=_string_to_value_type(data.get(CONF_VALUE_TYPE)),
        value_unit=data.get(CONF_UNIT_OF_MEASUREMENT),
        value_min=data.get(CONF_VALUE_MIN),
        value_max=data.get(CONF_VALUE_MAX),
        value_renderer=get_value_renderer(hass, value_template)
        if (value_template := data.get(CONF_VALUE_TEMPLATE))
        else None,
        command_set=Command(data[CONF_COMMAND_SET], renderer=get_command_renderer(hass))
        if data.get(CONF_COMMAND_SET)
        else None,
        command_on=Command(data[CONF_COMMAND_ON], renderer=get_command_renderer(hass))
        if data.get(CONF_COMMAND_ON)
        else None,
        command_off=Command(data[CONF_COMMAND_OFF], renderer=get_command_renderer(hass))
        if data.get(CONF_COMMAND_OFF)
        else None,
        payload_on=data.get(CONF_PAYLOAD_ON),
        payload_off=data.get(CONF_PAYLOAD_OFF),
        options=options,
    )

    if isinstance(sensor, DynamicSensor):
        sensor.separator = data.get(CONF_SEPARATOR)

    return sensor


def _sensor_command_to_conf(command: SensorCommand) -> dict:
    return _remove_none_items(
        {
            CONF_COMMAND: command.string,
            CONF_TIMEOUT: command.timeout,
            CONF_SCAN_INTERVAL: command.interval,
            CONF_SENSORS: [_sensor_to_conf(sensor) for sensor in command.sensors],
        }
    )


def _conf_to_sensor_command(hass: HomeAssistant, data: dict) -> SensorCommand:
    return SensorCommand(
        data[CONF_COMMAND],
        [_conf_to_sensor(hass, sensor_data) for sensor_data in data[CONF_SENSORS]],
        timeout=data.get(CONF_TIMEOUT),
        renderer=get_command_renderer(hass),
        interval=data.get(CONF_SCAN_INTERVAL),
    )


def get_action_commands_conf(remote: Remote) -> list[dict]:
    """Get action commands conf."""
    return [_action_command_to_conf(command) for command in remote.action_commands]


def get_sensor_commands_conf(remote: Remote) -> list[dict]:
    """Get sensor commands conf."""
    return [_sensor_command_to_conf(command) for command in remote.sensor_commands]


def get_command_set(hass: HomeAssistant, options: dict) -> CommandSet:
    """Get command set."""
    return CommandSet(
        "",
        [
            _conf_to_action_command(hass, command_data)
            for command_data in options[CONF_ACTION_COMMANDS]
        ],
        [
            _conf_to_sensor_command(hass, command_data)
            for command_data in options[CONF_SENSOR_COMMANDS]
        ],
    )
