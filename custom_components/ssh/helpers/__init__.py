from __future__ import annotations

import asyncio
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
    CONF_TIMEOUT,
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
    CONF_KEY,
    CONF_UPDATE_INTERVAL,
    SERVICE_EXECUTE_COMMAND,
    SERVICE_POLL_SENSOR,
    SERVICE_RUN_ACTION,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from .coordinator import SensorCommandCoordinator, StateCoordinator
from .helpers import get_command_renderer

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


async def async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await entry.async_unload(hass)
    await entry.async_setup(hass)


def async_register_services(hass: HomeAssistant, domain: str):
    def get_response(coro: Coroutine):
        @wraps(coro)
        async def wrapper(call: ServiceCall) -> ServiceResponse:
            entry_ids = await async_extract_config_entry_ids(hass, call)
            data = await asyncio.gather(
                *(coro(hass.data[domain][entry_id], call) for entry_id in entry_ids)
            )
            return {"results": [result for results in data for result in results]}

        return wrapper

    def get_command_result(coro: Coroutine):
        @wraps(coro)
        async def wrapper(entry_data: EntryData, call: ServiceCall) -> list[dict]:
            try:
                output: CommandOutput = await coro(entry_data, call)
            except Exception as exc:  # pylint: disable=broad-except
                result = {
                    "device_id": entry_data.device_entry.id,
                    "device_name": entry_data.device_entry.name,
                    "success": False,
                    "error": str(exc),
                }
            else:
                result = {
                    "device_id": entry_data.device_entry.id,
                    "device_name": entry_data.device_entry.name,
                    "success": True,
                    "command": output.command_string,
                    "stdout": output.stdout,
                    "stderr": output.stderr,
                    "code": output.code,
                }
            return [result]

        return wrapper

    @get_response
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

    @get_response
    @get_command_result
    async def run_action(entry_data: EntryData, call: ServiceCall) -> CommandOutput:
        action_key = call.data[CONF_KEY]
        variables = call.data.get(CONF_VARIABLES)
        return await entry_data.manager.async_run_action(action_key, variables)

    @get_response
    async def poll_sensor(entry_data: EntryData, call: ServiceCall) -> list[dict]:
        entities = [
            entity
            for platform in entity_platform.async_get_platforms(hass, domain)
            for entity in platform.entities.values()
            if isinstance(entity, BaseSensorEntity)
            and entity.coordinator == entry_data.state_coordinator
        ]
        selected_entities = await async_extract_entities(hass, entities, call)
        sensor_keys = [entity.key for entity in selected_entities]
        sensors = await entry_data.manager.async_poll_sensors(sensor_keys)
        return [
            {
                "entity_id": entity.entity_id,
                "entity_name": entity.name,
                "success": sensors[i].value is not None,
            }
            for i, entity in enumerate(selected_entities)
        ]

    @get_response
    async def turn_on(entry_data: EntryData, call: ServiceCall) -> list[dict]:
        try:
            await entry_data.manager.async_turn_on()
        except Exception as exc:  # pylint: disable=broad-except
            result = {
                "device_id": entry_data.device_entry.id,
                "device_name": entry_data.device_entry.name,
                "success": False,
                "error": str(exc),
            }
        else:
            result = {
                "device_id": entry_data.device_entry.id,
                "device_name": entry_data.device_entry.name,
                "success": True,
            }
        return [result]

    @get_response
    @get_command_result
    async def turn_off(entry_data: EntryData, call: ServiceCall) -> CommandOutput:
        return await entry_data.manager.async_turn_off()

    hass.services.async_register(
        domain,
        SERVICE_EXECUTE_COMMAND,
        execute_command,
        EXECUTE_COMMAND_SCHEMA,
        SupportsResponse.ONLY,
    )

    hass.services.async_register(
        domain,
        SERVICE_RUN_ACTION,
        run_action,
        RUN_ACTION_SCHEMA,
        SupportsResponse.ONLY,
    )

    hass.services.async_register(
        domain,
        SERVICE_POLL_SENSOR,
        poll_sensor,
        None,
        SupportsResponse.ONLY,
    )

    hass.services.async_register(
        domain,
        SERVICE_TURN_ON,
        turn_on,
        None,
        SupportsResponse.ONLY,
    )

    hass.services.async_register(
        domain,
        SERVICE_TURN_OFF,
        turn_off,
        None,
        SupportsResponse.ONLY,
    )


async def async_initialize(
    hass: HomeAssistant,
    entry: ConfigEntry,
    manager: SSHManager,
    platforms: list[Platform],
):
    state_coordinator = StateCoordinator(
        hass, manager, entry.options[CONF_UPDATE_INTERVAL]
    )

    command_coordinators = [
        SensorCommandCoordinator(hass, manager, command)
        for command in manager.sensor_commands
        if command.interval
    ]

    entry_data = EntryData(manager, state_coordinator, command_coordinators)

    hass.data.setdefault(entry.domain, {})
    hass.data[entry.domain][entry.entry_id] = entry_data

    entry.async_on_unload(entry.add_update_listener(async_reload))
    await state_coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    registry: DeviceRegistry = device_registry.async_get(hass)
    device_entry = registry.async_get_device({(entry.domain, entry.unique_id)})
    entry_data.device_entry = device_entry

    async_register_services(hass, entry.domain)
