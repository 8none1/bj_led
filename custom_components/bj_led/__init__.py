from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, Event
from homeassistant.const import CONF_MAC, EVENT_HOMEASSISTANT_STOP

from .const import DOMAIN, CONF_RESET, CONF_DELAY, DEFAULT_DELAY
from .bjled import BJLEDInstance
import logging

LOGGER = logging.getLogger(__name__)
PLATFORMS = ["light"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    reset = entry.options.get(CONF_RESET, None) or entry.data.get(CONF_RESET, None)
    # Use an explicitly configured delay (including 0 = never disconnect),
    # otherwise fall back to DEFAULT_DELAY. Previously an unset delay meant
    # the connection was never closed.
    if CONF_DELAY in entry.options:
        delay = entry.options[CONF_DELAY]
    elif CONF_DELAY in entry.data:
        delay = entry.data[CONF_DELAY]
    else:
        delay = DEFAULT_DELAY
    LOGGER.debug("Config Reset data: %s and config delay data: %s", reset, delay)

    instance = BJLEDInstance(entry.data[CONF_MAC], reset, delay, hass)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = instance

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _async_stop(event: Event) -> None:
        """Close the connection."""
        await instance.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        instance = hass.data[DOMAIN][entry.entry_id]
        await instance.stop()
    hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    # Reload so changed options (e.g. disconnect delay) take effect immediately.
    await hass.config_entries.async_reload(entry.entry_id)
