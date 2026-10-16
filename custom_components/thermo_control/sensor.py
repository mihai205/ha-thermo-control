"""Sensors."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from . import ThermoConfigEntry
from .const import REASONS, SUBENTRY_ROOM
from .coordinator import Room, ThermoCoordinator
from .entity import ThermoHubEntity, ThermoRoomEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThermoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            RoomsCallingSensor(coordinator),
            BoilerLockoutSensor(coordinator),
            BoilerOnTimeSensor(coordinator),
        ]
    )
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_ROOM:
            continue
        room = coordinator.rooms[subentry.subentry_id]
        async_add_entities(
            [
                DemandReasonSensor(coordinator, room),
                TemperatureDeficitSensor(coordinator, room),
                HeatingTimeSensor(coordinator, room),
            ],
            config_subentry_id=subentry.subentry_id,
        )


class DemandReasonSensor(ThermoRoomEntity, SensorEntity):
    """Why the room does/doesn't demand."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = REASONS

    def __init__(self, coordinator: ThermoCoordinator, room: Room) -> None:
        """Initialise."""
        super().__init__(coordinator, room, "demand_reason")

    @property
    def native_value(self) -> str:
        """Reason."""
        return self.room.reason


class TemperatureDeficitSensor(ThermoRoomEntity, SensorEntity):
    """Target minus current."""

    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: ThermoCoordinator, room: Room) -> None:
        """Initialise."""
        super().__init__(coordinator, room, "temperature_deficit")

    @property
    def native_value(self) -> float | None:
        """Deficit."""
        return self.room.deficit


def _restore_seconds(last_state, today: str) -> float | None:
    """Parse a restored minutes value, only if from today."""
    if last_state is None or last_state.attributes.get("date") != today:
        return None
    try:
        return float(last_state.state) * 60
    except (TypeError, ValueError):
        return None


class HeatingTimeSensor(ThermoRoomEntity, SensorEntity, RestoreEntity):
    """Heating minutes today."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: ThermoCoordinator, room: Room) -> None:
        """Initialise."""
        super().__init__(coordinator, room, "heating_time_today")

    async def async_added_to_hass(self) -> None:
        """Restore today's total."""
        await super().async_added_to_hass()
        seconds = _restore_seconds(
            await self.async_get_last_state(), dt_util.now().date().isoformat()
        )
        if seconds is not None:
            self.room.heating_seconds = seconds

    @property
    def native_value(self) -> float:
        """Minutes."""
        return round(self.room.heating_seconds_now() / 60, 1)

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Date marker used for restore."""
        return {"date": dt_util.now().date().isoformat()}


class RoomsCallingSensor(ThermoHubEntity, SensorEntity):
    """Number of rooms demanding heat."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ThermoCoordinator) -> None:
        """Initialise."""
        super().__init__(coordinator, "rooms_calling")

    @property
    def native_value(self) -> int:
        """Count."""
        return len(self.coordinator.rooms_calling)

    @property
    def extra_state_attributes(self) -> dict[str, list[str]]:
        """Names."""
        return {"rooms": [room.name for room in self.coordinator.rooms_calling]}


class BoilerLockoutSensor(ThermoHubEntity, SensorEntity):
    """Seconds until boiler can switch."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(self, coordinator: ThermoCoordinator) -> None:
        """Initialise."""
        super().__init__(coordinator, "boiler_lockout_remaining")

    @property
    def native_value(self) -> int:
        """Remaining seconds."""
        return round(self.coordinator.lockout_remaining)


class BoilerOnTimeSensor(ThermoHubEntity, SensorEntity, RestoreEntity):
    """Boiler minutes on today."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: ThermoCoordinator) -> None:
        """Initialise."""
        super().__init__(coordinator, "boiler_on_time_today")

    async def async_added_to_hass(self) -> None:
        """Restore today's total."""
        await super().async_added_to_hass()
        seconds = _restore_seconds(
            await self.async_get_last_state(), dt_util.now().date().isoformat()
        )
        if seconds is not None:
            self.coordinator.boiler_seconds = seconds

    @property
    def native_value(self) -> float:
        """Minutes."""
        return round(self.coordinator.boiler_seconds_now() / 60, 1)

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Date marker used for restore."""
        return {"date": dt_util.now().date().isoformat()}


__all__ = ["Callable"]
