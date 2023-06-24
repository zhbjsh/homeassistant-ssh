"""The SSH integration."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging

from ssh_remote_control import Remote
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_COMMAND,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_TIMEOUT,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_platform
from homeassistant.helpers.service import (
    async_extract_config_entry_ids,
    async_extract_entities,
)

from .base_entity import BaseSensorEntity
from .const import (
    CONF_ALLOW_TURN_OFF,
    CONF_COMMAND_TIMEOUT,
    CONF_CONTEXT,
    CONF_KEY,
    CONF_PING_TIMEOUT,
    CONF_SSH_HOST_KEYS_FILE,
    CONF_SSH_KEY_FILE,
    CONF_SSH_PASSWORD,
    CONF_SSH_PORT,
    CONF_SSH_TIMEOUT,
    CONF_SSH_USER,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    SERVICE_CALL_SERVICE,
    SERVICE_EXECUTE_COMMAND,
    SERVICE_POLL_SENSOR,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from .coordinator import SensorCommandCoordinator, StateCoordinator
from .options_converter import get_command_set

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
]

EXECUTE_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COMMAND): str,
        vol.Optional(CONF_TIMEOUT): float,
        vol.Optional(CONF_CONTEXT): dict,
        vol.Optional(ATTR_DEVICE_ID): list,
        vol.Optional(ATTR_ENTITY_ID): list,
    }
)

CALL_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_KEY): str,
        vol.Optional(CONF_CONTEXT): dict,
        vol.Optional(ATTR_DEVICE_ID): list,
        vol.Optional(ATTR_ENTITY_ID): list,
    }
)


@dataclass
class EntryData:
    """The EntryData class."""

    remote: Remote
    state_coordinator: StateCoordinator
    command_coordinators: list[SensorCommandCoordinator]


async def _config_entry_listener(hass: HomeAssistant, entry: ConfigEntry):
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SSH from a config entry."""
    data = entry.data
    options = entry.options

    remote = Remote(
        data[CONF_HOST],
        name=data[CONF_NAME],
        mac_address=data[CONF_MAC],
        ssh_port=data[CONF_SSH_PORT],
        ssh_user=data.get(CONF_SSH_USER),
        ssh_password=data.get(CONF_SSH_PASSWORD),
        ssh_key_file=data.get(CONF_SSH_KEY_FILE),
        ssh_host_keys_file=data.get(CONF_SSH_HOST_KEYS_FILE),
        ssh_timeout=options[CONF_SSH_TIMEOUT],
        ping_timeout=options[CONF_PING_TIMEOUT],
        command_timeout=options[CONF_COMMAND_TIMEOUT],
        command_set=get_command_set(hass, options),
        allow_turn_off=options[CONF_ALLOW_TURN_OFF],
        logger=_LOGGER,
    )

    state_coordinator = StateCoordinator(hass, remote, options[CONF_UPDATE_INTERVAL])

    command_coordinators = [
        SensorCommandCoordinator(hass, remote, command)
        for command in remote.sensor_commands
        if command.interval
    ]

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = EntryData(
        remote, state_coordinator, command_coordinators
    )

    entry.async_on_unload(entry.add_update_listener(_config_entry_listener))
    await state_coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def turn_on(call: ServiceCall):
        config_entry_ids = await async_extract_config_entry_ids(hass, call)
        tasks = []

        for entry_id in config_entry_ids:
            entry_data: EntryData = hass.data[DOMAIN][entry_id]
            tasks.append(entry_data.state_coordinator.async_turn_on())

        if tasks:
            await asyncio.wait(tasks)

    async def turn_off(call: ServiceCall):
        config_entry_ids = await async_extract_config_entry_ids(hass, call)
        tasks = []

        for entry_id in config_entry_ids:
            entry_data: EntryData = hass.data[DOMAIN][entry_id]
            tasks.append(entry_data.state_coordinator.async_turn_off())

        if tasks:
            await asyncio.wait(tasks)

    async def execute_command(call: ServiceCall):
        config_entry_ids = await async_extract_config_entry_ids(hass, call)
        command_string = call.data[CONF_COMMAND]
        timeout = call.data.get(CONF_TIMEOUT)
        context = call.data.get(CONF_CONTEXT)
        tasks = []

        for entry_id in config_entry_ids:
            entry_data: EntryData = hass.data[DOMAIN][entry_id]
            tasks.append(
                entry_data.state_coordinator.async_execute_command(
                    command_string, timeout, context
                ),
            )

        if tasks:
            await asyncio.wait(tasks)

    async def call_service(call: ServiceCall):
        config_entry_ids = await async_extract_config_entry_ids(hass, call)
        service_key = call.data[CONF_KEY]
        context = call.data.get(CONF_CONTEXT)
        tasks = []

        for entry_id in config_entry_ids:
            entry_data: EntryData = hass.data[DOMAIN][entry_id]
            tasks.append(
                entry_data.state_coordinator.async_call_service(service_key, context)
            )

        if tasks:
            await asyncio.wait(tasks)

    async def poll_sensor(call: ServiceCall):
        sensor_entities: list[BaseSensorEntity] = []

        for platform in entity_platform.async_get_platforms(hass, DOMAIN):
            for entity in platform.entities.values():
                if isinstance(entity, BaseSensorEntity):
                    sensor_entities.append(entity)

        entities = await async_extract_entities(hass, sensor_entities, call)
        config_entry_ids = await async_extract_config_entry_ids(hass, call)
        entities_by_entry_id: dict[str, list[BaseSensorEntity]] = {
            entry_id: [] for entry_id in config_entry_ids
        }

        for entity in entities:
            entry_id = entity.coordinator.config_entry.entry_id
            entities_by_entry_id[entry_id].append(entity)

        tasks = []

        for entry_id, entities in entities_by_entry_id.items():
            entry_data: EntryData = hass.data[DOMAIN][entry_id]
            sensor_keys = [entity.key for entity in entities]

            if sensor_keys:
                tasks.append(
                    entry_data.state_coordinator.async_poll_sensors(sensor_keys)
                )

        if tasks:
            await asyncio.wait(tasks)

    hass.services.async_register(
        DOMAIN,
        SERVICE_TURN_ON,
        turn_on,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_TURN_OFF,
        turn_off,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_EXECUTE_COMMAND,
        execute_command,
        EXECUTE_COMMAND_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CALL_SERVICE,
        call_service,
        CALL_SERVICE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_POLL_SENSOR,
        poll_sensor,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry_data: EntryData = hass.data[DOMAIN].pop(entry.entry_id)
        entry_data.state_coordinator.stop()

        for coordinator in entry_data.command_coordinators:
            coordinator.stop()

        await entry_data.remote.async_disconnect()

    return unload_ok
