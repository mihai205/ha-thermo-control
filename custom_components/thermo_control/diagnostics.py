"""Diagnostics."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import ThermoConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ThermoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics."""
    coordinator = entry.runtime_data
    return {
        "config": dict(entry.data),
        "options": dict(entry.options),
        "boiler": {
            "heating": coordinator.boiler_heating,
            "any_demand": coordinator.any_demand,
            "lockout_remaining": coordinator.lockout_remaining,
        },
        "rooms": {
            room.subentry_id: {
                "name": room.name,
                "config": dict(entry.subentries[room.subentry_id].data),
                "target": room.target,
                "current": room.current,
                "preset": room.preset,
                "hvac_off": room.hvac_off,
                "demand": room.demand,
                "reason": room.reason,
                "window_open": room.window_open,
                "heating_seconds": room.heating_seconds_now(),
            }
            for room in coordinator.rooms.values()
        },
    }
