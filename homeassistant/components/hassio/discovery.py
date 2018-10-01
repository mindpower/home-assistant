"""Implement the serivces discovery feature from Hass.io for Add-ons."""
import asyncio
import logging
import os

import voluptuous as vol
from aiohttp import web
from aiohttp.web_exceptions import HTTPServiceUnavailable

from homeassistant.core import callback
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.components.http import HomeAssistantView

from .handler import HassioAPIError

_LOGGER = logging.getLogger(__name__)

ATTR_DISCOVERY = 'discovery'
ATTR_ADDON = 'addon'
ATTR_NAME = 'name'
ATTR_SERVICE = 'service'
ATTR_CONFIG = 'config'


@callback
def async_setup_discovery(hass, hassio):
    """Discovery setup."""
    hassio_discovery = HassIODiscovery(hass, hassio)

    # Handle exists discovery messages
    async def async_discovery_start_handler(event):
        """Process all exists discovery on startup."""
        try:
            data = await hassio.retrieve_discovery_messages()
        except HassioAPIError as err:
            _LOGGER.error(
                "Can't read discover info: %s", err)
            return

        for discovery in data[ATTR_DISCOVERY]:
            hass.async_create_taks(
                hassio_discovery.async_process_new(discovery))

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_START, async_discovery_start_handler)

    hass.http.register_view(hassio_discovery)


class HassIODiscovery(HomeAssistantView):
    """Hass.io view to handle base part."""

    name = "api:hassio_push:discovery"
    url = "/api/hassio_push/discovery/{uuid}"

    def __init__(self, hass, hassio):
        """Initialize WebView."""
        self.hass = hass
        self.hassio = hassio

    async def post(self, request):
        """Handle new discovery requests."""
        uuid = request.match_info.get(uuid)

        # Fetch discovery data and prevent injections
        try:
            data = await self.hassio.get_discovery_message(uuid)
        except HassioAPIError as err:
            _LOGGER.error("Can't read discovey data: %s", err)
            raise HTTPServiceUnavailable() from None

        await self.async_process_new(self, data)
        return web.Response()

    async def delete(self, request):
        """Handle remove discovery requests."""
        data = request.json()

        await self.async_process_del(self, data)
        return web.Response()

    async def async_process_new(self, data):
        """Process add discovery entry."""
        # Read addinional Add-on info
        try:
            addon_info = await self.hassio.get_addon_info(data[ATTR_ADDON])
        except HassioAPIError as err:
            _LOGGER.error("Can't read add-on info: %s", err)
            return

        # Replace Add-on name with ID
        data[ATTR_ADDON] = addon_info[ATTR_NAME]

        await hass.config_entries.flow.async_init(
            data[ATTR_SERVICE], context={'source': 'hassio'}, data=data[ATTR_CONFIG])

    async def async_process_del(self, data):
        """Process remove discovery entry."""
