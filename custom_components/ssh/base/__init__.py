from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from functools import wraps

import voluptuous as vol
from ssh_terminal_manager import (
    ActionKey,
    Command,
    CommandOutput,
    SensorKey,
    SSHManager,
)

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
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_platform
from homeassistant.helpers.service import (
    async_extract_config_entry_ids,
    async_extract_entities,
)

from .base_entity import BaseActionEntity, BaseEntity, BaseSensorEntity
from .const import (
    CONF_KEY,
    CONF_UPDATE_INTERVAL,
    SERVICE_EXECUTE_COMMAND,
    SERVICE_POLL_SENSOR,
    SERVICE_RUN_ACTION,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from .converter import Converter
from .coordinator import SensorCommandCoordinator, StateCoordinator
from .entry_data import EntryData
from .helpers import (
    get_child_add_handler,
    get_child_remove_handler,
    get_command_renderer,
    get_device_sensor_update_handler,
    get_value_renderer,
)

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


async def async_initialize_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    manager: SSHManager,
    platforms: list[Platform],
    ignored_action_keys: list[ActionKey] | None = None,
    ignored_sensor_keys: list[SensorKey] | None = None,
):
    """Initialize a config entry."""
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(entry.domain, entry.unique_id)},
        name=manager.name,
    )

    state_coordinator = StateCoordinator(
        hass, manager, entry.options[CONF_UPDATE_INTERVAL]
    )

    command_coordinators = [
        SensorCommandCoordinator(hass, manager, command)
        for command in manager.sensor_commands
        if command.interval
    ]

    entry_data = EntryData(
        entry,
        device_entry,
        manager,
        state_coordinator,
        command_coordinators,
        platforms,
        ignored_action_keys,
        ignored_sensor_keys,
    )

    handle_device_sensor_update = get_device_sensor_update_handler(
        hass, entry_data, device_registry
    )

    for key in SensorKey.OS_NAME, SensorKey.OS_VERSION, SensorKey.MACHINE_TYPE:
        if sensor := manager.sensors_by_key.get(key):
            sensor.on_update.subscribe(handle_device_sensor_update)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    hass.data.setdefault(entry.domain, {})
    hass.data[entry.domain][entry.entry_id] = entry_data

    await state_coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, platforms)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload a config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry_data: EntryData = hass.data[entry.domain][entry.entry_id]
    platforms = entry_data.platforms
    coordinators = entry_data.state_coordinator, *entry_data.command_coordinators

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, platforms):
        hass.data[entry.domain].pop(entry.entry_id)

        for coordinator in coordinators:
            coordinator.stop()

        await entry_data.manager.async_close()

    return unload_ok


def async_register_services(hass: HomeAssistant, domain: str):
    """Register the services for a domain."""

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
