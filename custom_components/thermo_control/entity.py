"""Base entities."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .coordinator import Room, ThermoCoordinator


class ThermoEntity(Entity):
    """Entity that refreshes when the coordinator evaluates."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: ThermoCoordinator) -> None:
        """Initialise."""
        self.coordinator = coordinator

    async def async_added_to_hass(self) -> None:
        """Register for coordinator updates."""
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.async_add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


class ThermoHubEntity(ThermoEntity):
    """Entity on the hub device."""

    def __init__(self, coordinator: ThermoCoordinator, key: str) -> None:
        """Initialise."""
        super().__init__(coordinator)
        entry_id = coordinator.entry.entry_id
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry_id)}, name="Thermo Control")


class ThermoRoomEntity(ThermoEntity):
    """Entity on a room device."""

    def __init__(self, coordinator: ThermoCoordinator, room: Room, key: str) -> None:
        """Initialise."""
        super().__init__(coordinator)
        self.room = room
        self._attr_translation_key = key
        self._attr_unique_id = f"{room.subentry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, room.subentry_id)}, name=room.name
        )
