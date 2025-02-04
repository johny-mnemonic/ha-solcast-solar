"""Support for Solcast PV forecast."""

import logging
import traceback
import dataclasses

from homeassistant import loader
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import (HomeAssistant,
                                ServiceCall,
                                ServiceResponse,
                                SupportsResponse,)
from homeassistant.helpers import aiohttp_client,service
from homeassistant.helpers.device_registry import async_get as device_registry
from homeassistant.util import dt as dt_util


from .const import (DOMAIN,
                    SERVICE_CLEAR_DATA, SERVICE_UPDATE, SERVICE_GET_FORECASTS, SOLCAST_URL)
from .coordinator import SolcastUpdateCoordinator
from .solcastapi import ConnectionOptions, SolcastApi

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up solcast parameters."""

    try:

        options = ConnectionOptions(
            entry.options[CONF_API_KEY],
            SOLCAST_URL,
            hass.config.path('solcast.json'),
            dt_util.get_time_zone(hass.config.time_zone)
        )

        solcast = SolcastApi(aiohttp_client.async_get_clientsession(hass), options)
        await solcast.sites_data()
        await solcast.sites_usage()
        await solcast.load_saved_data()
        
        coordinator = SolcastUpdateCoordinator(hass, solcast) 
        await coordinator.setup()

        await coordinator.async_config_entry_first_refresh()
        #await _async_migrate_unique_ids(hass, entry, coordinator)

        entry.async_on_unload(entry.add_update_listener(async_update_options))

        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

        _VERSION = ""
        try:
            integration = await loader.async_get_integration(hass, DOMAIN)
            _VERSION = str(integration.version)
            _LOGGER.info(f"Solcast Integration version number: {_VERSION}")
        except loader.IntegrationNotFound:
            _VERSION = ""

        if _VERSION is None:
            _VERSION = ""

        coordinator._version = _VERSION
        
        _LOGGER.info(f"SOLCAST - Solcast API data UTC times are converted to {hass.config.time_zone}")

        #hass.config_entries.async_setup_platforms(entry, PLATFORMS)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        async def handle_service_update_forecast(call):
            """Handle service call"""
            _LOGGER.info(f"SOLCAST - Service call: {SERVICE_UPDATE}")
            await coordinator.service_event_update()

        async def handle_service_clear_solcast_data(call):
            """Handle service call"""
            _LOGGER.info(f"SOLCAST - Service call: {SERVICE_CLEAR_DATA}")
            await coordinator.service_event_delete_old_solcast_json_file()
            
        async def handle_service_get_solcast_data(call) -> ServiceResponse:
            """Handle service call"""
            _LOGGER.info(f"SOLCAST - Service call: {SERVICE_GET_FORECASTS}")
            d = await coordinator.service_get_forecasts()
            return {
                "data": [
                    d
                ]
            }

        hass.services.async_register(
            DOMAIN, SERVICE_UPDATE, handle_service_update_forecast
        )

        hass.services.async_register(
            DOMAIN, SERVICE_CLEAR_DATA, handle_service_clear_solcast_data
        )
        
        hass.services.async_register(
            DOMAIN, "get_forecasts", handle_service_get_solcast_data,None,SupportsResponse.ONLY,
        )

        

        return True

    except Exception as err:
        _LOGGER.error("SOLCAST - async_setup_entry: %s - Err Msg: %s",traceback.format_exc(), err)
        return False

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    try:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        if unload_ok:
            hass.data[DOMAIN].pop(entry.entry_id)

        hass.services.async_remove(DOMAIN, SERVICE_UPDATE)
        hass.services.async_remove(DOMAIN, SERVICE_CLEAR_DATA)
        hass.services.async_remove(DOMAIN, SERVICE_GET_FORECASTS)

        return unload_ok
    except Exception as err:
        _LOGGER.error("SOLCAST - async_unload_entry: %s - Err Msg: %s",traceback.format_exc(), err.message)

async def async_remove_config_entry_device(hass: HomeAssistant, entry: ConfigEntry, device) -> bool:
    try:
        device_registry(hass).async_remove_device(device.id)
        return True
    except Exception as err:
        _LOGGER.error("SOLCAST - async_remove_config_entry_device: %s - Err Msg: %s",traceback.format_exc(), err)

# async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
#     """Handle removal of an entry."""
#     try:
#         

#     except Exception as err:
#         _LOGGER.error("SOLCAST - async_remove_entry: %s - Err Msg: %s",traceback.format_exc(), err.message)

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry):
    """Reload entry if options change."""
    try:
        _LOGGER.debug("Reloading entry %s", entry.entry_id)

        await hass.config_entries.async_reload(entry.entry_id)
    except Exception as err:
        _LOGGER.error("SOLCAST - async_update_options: %s - Err Msg: %s",traceback.format_exc(), err)

async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    try:
        _LOGGER.debug("Solcast Config Migrating from version %s", config_entry.version)

        #remove this when it ever changes again
        config_entry.version = 3
        
        # if config_entry.version == 2:
        #     #new_data = {**config_entry.options}
        #     new_data = {**config_entry.options, CONST_DISABLEAUTOPOLL: False}

        #     config_entry.version = 3
        #     hass.config_entries.async_update_entry(config_entry, options=new_data)

        _LOGGER.debug("Solcast Config Migration to version %s successful", config_entry.version)
        return True
    except Exception as err:
        _LOGGER.error("SOLCAST - async_migrate_entry error:  %s - Err Msg: %s",traceback.format_exc(), err)
        return False