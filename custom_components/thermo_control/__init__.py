"""Thermo Control integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import ThermoCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
]

type ThermoConfigEntry = ConfigEntry[ThermoCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ThermoConfigEntry) -> bool:
    """Set up Thermo Control from a config entry."""
    coordinator = ThermoCoordinator(hass, entry)
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(coordinator.async_stop)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    coordinator.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ThermoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: ThermoConfigEntry) -> None:
    """Reload on options or subentry changes."""
    await hass.config_entries.async_reload(entry.entry_id)
