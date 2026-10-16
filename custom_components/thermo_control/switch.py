"""Boost switch."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ThermoConfigEntry
from .const import SUBENTRY_ROOM
from .coordinator import Room, ThermoCoordinator
from .entity import ThermoRoomEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThermoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up boost switches."""
    coordinator = entry.runtime_data
    for subentry in entry.subentries.values():
        if subentry.subentry_type == SUBENTRY_ROOM:
            async_add_entities(
                [BoostSwitch(coordinator, coordinator.rooms[subentry.subentry_id])],
                config_subentry_id=subentry.subentry_id,
            )


class BoostSwitch(ThermoRoomEntity, SwitchEntity):
    """Boost heating for a limited time."""

    def __init__(self, coordinator: ThermoCoordinator, room: Room) -> None:
        """Initialise."""
        super().__init__(coordinator, room, "boost")

    @property
    def is_on(self) -> bool:
        """Boost active."""
        return self.room.boost_active

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start boost."""
        self.room.start_boost()
        self.coordinator.async_evaluate()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """End boost."""
        self.room.end_boost()
        self.coordinator.async_evaluate()
        self.async_write_ha_state()
