"""Room climate entity."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import ThermoConfigEntry
from .const import (
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    SUBENTRY_ROOM,
)
from .coordinator import Room, ThermoCoordinator
from .entity import ThermoRoomEntity

PRESETS = [PRESET_COMFORT, PRESET_ECO, PRESET_AWAY, PRESET_BOOST, PRESET_NONE]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThermoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up room climates."""
    coordinator = entry.runtime_data
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_ROOM:
            continue
        room = coordinator.rooms[subentry.subentry_id]
        async_add_entities(
            [ThermoRoomClimate(coordinator, room)],
            config_subentry_id=subentry.subentry_id,
        )


class ThermoRoomClimate(ThermoRoomEntity, ClimateEntity, RestoreEntity):
    """Virtual room thermostat."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = PRESETS
    _attr_min_temp = 5.0
    _attr_max_temp = 30.0
    _attr_target_temperature_step = 0.5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator: ThermoCoordinator, room: Room) -> None:
        """Initialise."""
        super().__init__(coordinator, room, "room")

    async def async_added_to_hass(self) -> None:
        """Restore previous state."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is None:
            return
        target = last.attributes.get(ATTR_TEMPERATURE)
        try:
            target = float(target) if target is not None else None
        except (TypeError, ValueError):
            target = None
        self.room.restore(
            target,
            last.state == HVACMode.OFF,
            last.attributes.get("preset_mode"),
        )

    @property
    def current_temperature(self) -> float | None:
        """Mean temperature."""
        return self.room.current

    @property
    def target_temperature(self) -> float:
        """Target."""
        return self.room.target

    @property
    def hvac_mode(self) -> HVACMode:
        """Mode."""
        return HVACMode.OFF if self.room.hvac_off else HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        """Action."""
        if self.room.hvac_off:
            return HVACAction.OFF
        return HVACAction.HEATING if self.room.demand else HVACAction.IDLE

    @property
    def preset_mode(self) -> str:
        """Preset."""
        return self.room.preset

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Extra attributes."""
        return {
            "demand": self.room.demand,
            "reason": self.room.reason,
            "deficit": self.room.deficit,
            "window_open": self.room.window_open,
        }

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set manual target."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        self.room.set_target(temperature)
        self.coordinator.async_evaluate()
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set mode."""
        self.room.set_hvac_off(hvac_mode == HVACMode.OFF)
        self.coordinator.async_evaluate()
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset."""
        self.room.set_preset(preset_mode)
        self.coordinator.async_evaluate()
        self.async_write_ha_state()
