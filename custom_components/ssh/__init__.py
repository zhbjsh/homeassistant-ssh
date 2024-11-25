from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from functools import wraps
import logging

from ssh_terminal_manager import (
    ActionKey,
    Command,
    CommandOutput,
    SensorKey,
    SSHManager,
)
import voluptuous as vol

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
from homeassistant.helpers import device_registry as dr, entity_platform
from homeassistant.helpers.service import (
    async_extract_config_entry_ids,
    async_extract_entities,
)

from .base_entity import BaseActionEntity, BaseEntity, BaseSensorEntity
from .const import (
    CONF_ALLOW_TURN_OFF,
    CONF_COMMAND_TIMEOUT,
    CONF_DISCONNECT_MODE,
    CONF_HOST_KEYS_FILENAME,
    CONF_INVOKE_SHELL,
    CONF_KEY,
    CONF_KEY_FILENAME,
    CONF_LOAD_SYSTEM_HOST_KEYS,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    SERVICE_EXECUTE_COMMAND,
    SERVICE_POLL_SENSOR,
    SERVICE_RESTART,
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

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
]

DEVICE_SENSOR_KEYS = [
    SensorKey.MACHINE_TYPE,
    SensorKey.OS_NAME,
    SensorKey.OS_VERSION,
    SensorKey.DEVICE_NAME,
    SensorKey.DEVICE_MODEL,
    SensorKey.MANUFACTURER,
    SensorKey.CPU_NAME,
    SensorKey.CPU_CORES,
    SensorKey.CPU_HARDWARE,
    SensorKey.CPU_MODEL,
    SensorKey.TOTAL_MEMORY,
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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        entry.version,
        entry.minor_version,
    )

    if entry.version > 1:
        return False

    if entry.version == 1:
        new_data = {**entry.data}
        new_options = {**entry.options}

        if entry.minor_version < 2:
            new_data[CONF_LOAD_SYSTEM_HOST_KEYS] = True
            new_options[CONF_DISCONNECT_MODE] = False

        if entry.minor_version < 3:
            new_data[CONF_INVOKE_SHELL] = False

        hass.config_entries.async_update_entry(
            entry, data=new_data, options=new_options, minor_version=3, version=1
        )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        entry.version,
        entry.minor_version,
    )

    return True


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
        load_system_host_keys=data[CONF_LOAD_SYSTEM_HOST_KEYS],
        invoke_shell=data[CONF_INVOKE_SHELL],
        allow_turn_off=options[CONF_ALLOW_TURN_OFF],
        command_timeout=options[CONF_COMMAND_TIMEOUT],
        disconnect_mode=options[CONF_DISCONNECT_MODE],
        collection=Converter(hass).get_collection(options),
        logger=_LOGGER,
    )

    manager.set_mac_address(data[CONF_MAC])

    await manager.async_load_host_keys()

    await async_initialize_entry(
        hass,
        entry,
        manager,
        PLATFORMS,
        ignored_action_keys=[ActionKey.TURN_OFF],
    )

    async_register_services(hass, DOMAIN)

    return True


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
            await coordinator.async_shutdown()

        await entry_data.manager.async_close()

    return unload_ok


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

    for key in DEVICE_SENSOR_KEYS:
        if sensor := manager.sensors_by_key.get(key):
            sensor.on_update.subscribe(handle_device_sensor_update)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    hass.data.setdefault(entry.domain, {})
    hass.data[entry.domain][entry.entry_id] = entry_data

    await state_coordinator.async_config_entry_first_refresh()

    if manager.disconnect_mode:
        await manager.async_update_sensor_commands(force=True)

    await hass.config_entries.async_forward_entry_setups(entry, platforms)


def async_register_services(hass: HomeAssistant, domain: str):
    """Register the domain services."""

    def get_response(coro: Coroutine):
        @wraps(coro)
        async def wrapper(call: ServiceCall) -> ServiceResponse | None:
            entry_ids = await async_extract_config_entry_ids(hass, call)
            data = await asyncio.gather(
                *(coro(hass.data[domain][entry_id], call) for entry_id in entry_ids)
            )
            return (
                {"results": [result for results in data for result in results]}
                if call.return_response
                else None
            )

        return wrapper

    def get_command_result(coro: Coroutine):
        @wraps(coro)
        async def wrapper(entry_data: EntryData, call: ServiceCall) -> list[dict]:
            try:
                output: CommandOutput = await coro(entry_data, call)
            except Exception as exc:  # noqa: BLE001
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

    def get_generic_result(coro: Coroutine):
        @wraps(coro)
        async def wrapper(entry_data: EntryData, call: ServiceCall) -> list[dict]:
            try:
                await coro(entry_data, call)
            except Exception as exc:  # noqa: BLE001
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
    @get_generic_result
    async def turn_on(entry_data: EntryData, call: ServiceCall) -> None:
        await entry_data.state_coordinator.async_turn_on()

    @get_response
    @get_command_result
    async def turn_off(entry_data: EntryData, call: ServiceCall) -> CommandOutput:
        return await entry_data.state_coordinator.async_turn_off()

    @get_response
    @get_command_result
    async def restart(entry_data: EntryData, call: ServiceCall) -> CommandOutput:
        return await entry_data.state_coordinator.async_restart()

    hass.services.async_register(
        domain,
        SERVICE_EXECUTE_COMMAND,
        execute_command,
        EXECUTE_COMMAND_SCHEMA,
        SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        domain,
        SERVICE_RUN_ACTION,
        run_action,
        RUN_ACTION_SCHEMA,
        SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        domain,
        SERVICE_POLL_SENSOR,
        poll_sensor,
        None,
        SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        domain,
        SERVICE_TURN_ON,
        turn_on,
        None,
        SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        domain,
        SERVICE_TURN_OFF,
        turn_off,
        None,
        SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        domain,
        SERVICE_RESTART,
        restart,
        None,
        SupportsResponse.OPTIONAL,
    )
