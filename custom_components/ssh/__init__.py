"""The SSH integration."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from dataclasses import dataclass
from functools import wraps

import voluptuous as vol
from ssh_terminal_manager import Command, CommandOutput, SSHManager

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
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers import device_registry, entity_platform
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
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
    device_entry: DeviceEntry | None = None


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

    manager.set_mac_address(data[CONF_MAC])

    state_coordinator = StateCoordinator(hass, manager, options[CONF_UPDATE_INTERVAL])

    command_coordinators = [
        SensorCommandCoordinator(hass, manager, command)
        for command in manager.sensor_commands
        if command.interval
    ]

    entry_data = EntryData(manager, state_coordinator, command_coordinators)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry_data

    entry.async_on_unload(entry.add_update_listener(update_listener))
    await state_coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    registry: DeviceRegistry = device_registry.async_get(hass)
    device_entry = registry.async_get_device({(DOMAIN, entry.unique_id)})
    entry_data.device_entry = device_entry

    def gather_results(coro: Coroutine):
        @wraps(coro)
        async def wrapper(call: ServiceCall) -> ServiceResponse:
            entry_ids = await async_extract_config_entry_ids(hass, call)
            results: list[dict] = await asyncio.gather(
                *(coro(hass.data[DOMAIN][entry_id], call) for entry_id in entry_ids)
            )
            return {id: data for result in results for id, data in result.items()}

        return wrapper

    def get_command_result(coro: Coroutine):
        @wraps(coro)
        async def wrapper(entry_data: EntryData, call: ServiceCall) -> dict[str, dict]:
            device_id = entry_data.device_entry.id
            try:
                output: CommandOutput = await coro(entry_data, call)
            except Exception as exc:  # pylint: disable=broad-except
                return {device_id: {"success": False, "error": str(exc)}}
            return {
                device_id: {
                    "success": True,
                    "stdout": output.stdout,
                    "stderr": output.stderr,
                    "code": output.code,
                }
            }

        return wrapper

    @gather_results
    async def turn_on(entry_data: EntryData, call: ServiceCall) -> dict[str, dict]:
        device_id = entry_data.device_entry.id
        try:
            await entry_data.manager.async_turn_on()
        except Exception as exc:  # pylint: disable=broad-except
            return {device_id: {"success": False, "error": str(exc)}}
        return {device_id: {"success": True}}

    @gather_results
    @get_command_result
    async def turn_off(entry_data: EntryData, call: ServiceCall):
        return await entry_data.manager.async_turn_off()

    @gather_results
    @get_command_result
    async def execute_command(
        entry_data: EntryData, call: ServiceCall
    ) -> CommandOutput:
        command = Command(
            call.data[CONF_COMMAND],
            timeout=call.data.get(CONF_TIMEOUT),
            renderer=get_command_renderer(hass),
        )
        variables = call.data.get(CONF_VARIABLES)
        return await entry_data.manager.async_execute_command(command, variables)

    @gather_results
    @get_command_result
    async def run_action(entry_data: EntryData, call: ServiceCall) -> CommandOutput:
        action_key = call.data[CONF_KEY]
        variables = call.data.get(CONF_VARIABLES)
        return await entry_data.manager.async_run_action(action_key, variables)

    @gather_results
    async def poll_sensor(entry_data: EntryData, call: ServiceCall) -> CommandOutput:
        entities = [
            entity
            for platform in entity_platform.async_get_platforms(hass, DOMAIN)
            for entity in platform.entities.values()
            if isinstance(entity, BaseSensorEntity)
            and entity.coordinator == entry_data.state_coordinator
        ]
        selected_entities = await async_extract_entities(hass, entities, call)
        sensor_keys = [entity.key for entity in selected_entities]
        sensors = await entry_data.manager.async_poll_sensors(sensor_keys)
        return {
            entity.entity_id: {"success": sensors[i].value is not None}
            for i, entity in enumerate(selected_entities)
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_TURN_ON,
        turn_on,
        None,
        SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_TURN_OFF,
        turn_off,
        None,
        SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_EXECUTE_COMMAND,
        execute_command,
        EXECUTE_COMMAND_SCHEMA,
        SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_RUN_ACTION,
        run_action,
        RUN_ACTION_SCHEMA,
        SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_POLL_SENSOR,
        poll_sensor,
        None,
        SupportsResponse.ONLY,
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
