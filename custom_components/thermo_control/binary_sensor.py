"""Binary sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ThermoConfigEntry
from .const import SUBENTRY_ROOM
from .coordinator import Room, ThermoCoordinator
from .entity import ThermoHubEntity, ThermoRoomEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThermoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities([BoilerDemandSensor(coordinator)])
    for subentry in entry.subentries.values():
        if subentry.subentry_type == SUBENTRY_ROOM:
            async_add_entities(
                [HeatDemandSensor(coordinator, coordinator.rooms[subentry.subentry_id])],
                config_subentry_id=subentry.subentry_id,
            )


class HeatDemandSensor(ThermoRoomEntity, BinarySensorEntity):
    """Room heat demand."""

    _attr_device_class = BinarySensorDeviceClass.HEAT

    def __init__(self, coordinator: ThermoCoordinator, room: Room) -> None:
        """Initialise."""
        super().__init__(coordinator, room, "heat_demand")

    @property
    def is_on(self) -> bool:
        """Demand."""
        return self.room.demand


class BoilerDemandSensor(ThermoHubEntity, BinarySensorEntity):
    """Boiler demand."""

    def __init__(self, coordinator: ThermoCoordinator) -> None:
        """Initialise."""
        super().__init__(coordinator, "boiler_demand")

    @property
    def is_on(self) -> bool:
        """Any room demands heat."""
        return self.coordinator.any_demand

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Boiler status."""
        return {"boiler_heating": self.coordinator.boiler_heating}
