"""The SSH integration."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import voluptuous as vol
from ssh_terminal_manager import Command, CommandError, SSHManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_COMMAND,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VARIABLES,
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
    CONF_HOST_KEYS_FILENAME,
    CONF_KEY,
    CONF_KEY_FILENAME,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    SERVICE_EXECUTE_COMMAND,
    SERVICE_POLL_SENSOR,
    SERVICE_RUN_ACTION,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from .converter import get_collection
from .coordinator import SensorCommandCoordinator, StateCoordinator
from .helpers import get_command_renderer

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.TEXT,
]

EXECUTE_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COMMAND): str,
        vol.Optional(CONF_TIMEOUT): int,
        vol.Optional(CONF_VARIABLES): dict,
        vol.Optional(ATTR_DEVICE_ID): list,
        vol.Optional(ATTR_ENTITY_ID): list,
    }
)

RUN_ACTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_KEY): str,
        vol.Optional(CONF_VARIABLES): dict,
        vol.Optional(ATTR_DEVICE_ID): list,
        vol.Optional(ATTR_ENTITY_ID): list,
    }
)


@dataclass
class EntryData:
    manager: SSHManager
    state_coordinator: StateCoordinator
    command_coordinators: list[SensorCommandCoordinator]


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SSH from a config entry."""
    data = entry.data
    options = entry.options

    manager = SSHManager(
        data[CONF_HOST],
        name=data[CONF_NAME],
        mac_address=data[CONF_MAC],
        port=data[CONF_PORT],
        username=data.get(CONF_USERNAME),
        password=data.get(CONF_PASSWORD),
        key_filename=data.get(CONF_KEY_FILENAME),
        host_keys_filename=data.get(CONF_HOST_KEYS_FILENAME),
        allow_turn_off=options[CONF_ALLOW_TURN_OFF],
        command_timeout=options[CONF_COMMAND_TIMEOUT],
        collection=get_collection(hass, options),
        logger=_LOGGER,
    )

    state_coordinator = StateCoordinator(hass, manager, options[CONF_UPDATE_INTERVAL])

    command_coordinators = [
        SensorCommandCoordinator(hass, manager, command)
        for command in manager.sensor_commands
        if command.interval
    ]

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = EntryData(
        manager, state_coordinator, command_coordinators
    )

    entry.async_on_unload(entry.add_update_listener(update_listener))
    await state_coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def turn_on(call: ServiceCall):
        async def func(entry_id: str):
            entry_data: EntryData = hass.data[DOMAIN][entry_id]
            await entry_data.manager.async_turn_on()

        await asyncio.wait(
            [
                func(entry_id)
                for entry_id in await async_extract_config_entry_ids(hass, call)
            ]
        )

    async def turn_off(call: ServiceCall):
        async def func(entry_id: str):
            entry_data: EntryData = hass.data[DOMAIN][entry_id]
            try:
                await entry_data.manager.async_turn_off()
            except CommandError:
                pass

        await asyncio.wait(
            [
                func(entry_id)
                for entry_id in await async_extract_config_entry_ids(hass, call)
            ]
        )

    async def execute_command(call: ServiceCall):
        command_string = call.data[CONF_COMMAND]
        timeout = call.data.get(CONF_TIMEOUT)
        variables = call.data.get(CONF_VARIABLES)
        command = Command(
            command_string,
            timeout=timeout,
            renderer=get_command_renderer(hass),
        )

        async def func(entry_id: str):
            entry_data: EntryData = hass.data[DOMAIN][entry_id]
            try:
                await entry_data.manager.async_execute_command(command, variables)
            except CommandError:
                pass

        await asyncio.wait(
            [
                func(entry_id)
                for entry_id in await async_extract_config_entry_ids(hass, call)
            ]
        )

    async def run_action(call: ServiceCall):
        action_key = call.data[CONF_KEY]
        variables = call.data.get(CONF_VARIABLES)

        async def func(entry_id: str):
            entry_data: EntryData = hass.data[DOMAIN][entry_id]
            try:
                await entry_data.manager.async_run_action(action_key, variables)
            except CommandError:
                pass

        await asyncio.wait(
            [
                func(entry_id)
                for entry_id in await async_extract_config_entry_ids(hass, call)
            ]
        )

    async def poll_sensor(call: ServiceCall):
        sensor_entities = [
            entity
            for platform in entity_platform.async_get_platforms(hass, DOMAIN)
            for entity in platform.entities.values()
            if isinstance(entity, BaseSensorEntity)
        ]

        entities_by_entry_id: dict[str, list[BaseSensorEntity]] = {
            entry_id: []
            for entry_id in await async_extract_config_entry_ids(hass, call)
        }

        for entity in await async_extract_entities(hass, sensor_entities, call):
            entry_id = entity.coordinator.config_entry.entry_id
            entities_by_entry_id[entry_id].append(entity)

        async def func(entry_id: str, entities: list[BaseSensorEntity]):
            entry_data: EntryData = hass.data[DOMAIN][entry_id]
            sensor_keys = [entity.key for entity in entities]
            await entry_data.manager.async_poll_sensors(sensor_keys)

        await asyncio.wait(
            [
                func(entry_id, entities)
                for entry_id, entities in entities_by_entry_id.items()
            ]
        )

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
        SERVICE_RUN_ACTION,
        run_action,
        RUN_ACTION_SCHEMA,
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

        await entry_data.manager.async_disconnect()

    return unload_ok
