"""Coordinator: room controllers and boiler control."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AWAY_TEMP,
    CONF_BOILER_CLIMATE,
    CONF_BOILER_HEAT_TEMP,
    CONF_BOILER_IDLE_TEMP,
    CONF_BOOST_MINUTES,
    CONF_COMFORT_TEMP,
    CONF_DEFAULT_HYSTERESIS,
    CONF_ECO_TEMP,
    CONF_HYSTERESIS,
    CONF_MIN_OFF_MINUTES,
    CONF_MIN_ON_MINUTES,
    CONF_SCHEDULE,
    CONF_TEMP_SENSORS,
    CONF_TRV_HEAT_TEMP,
    CONF_TRV_IDLE_TEMP,
    CONF_TRVS,
    CONF_WINDOW_DELAY,
    CONF_WINDOW_SENSORS,
    DEFAULT_AWAY_TEMP,
    DEFAULT_BOILER_HEAT_TEMP,
    DEFAULT_BOILER_IDLE_TEMP,
    DEFAULT_BOOST_MINUTES,
    DEFAULT_COMFORT_TEMP,
    DEFAULT_ECO_TEMP,
    DEFAULT_HYSTERESIS,
    DEFAULT_MIN_OFF_MINUTES,
    DEFAULT_MIN_ON_MINUTES,
    DEFAULT_TRV_HEAT_TEMP,
    DEFAULT_TRV_IDLE_TEMP,
    DEFAULT_WINDOW_DELAY,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    REASON_OFF,
    REASON_SATISFIED,
    SAFETY_INTERVAL_MINUTES,
    SETPOINT_TOLERANCE,
    SUBENTRY_ROOM,
)
from .logic import boiler_action, compute_demand, trv_setpoint

_LOGGER = logging.getLogger(__name__)

_NEVER = 1e12


def _valid_number(value: Any) -> float | None:
    """Parse a numeric state."""
    if value in (None, STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class Room:
    """Runtime state and control of one room."""

    def __init__(self, coordinator: ThermoCoordinator, subentry: ConfigSubentry):
        """Initialise from a room subentry."""
        self.coordinator = coordinator
        self.hass = coordinator.hass
        self.subentry_id = subentry.subentry_id
        self.name = subentry.title
        data = subentry.data
        self.temp_sensors: list[str] = list(data.get(CONF_TEMP_SENSORS, []))
        self.trvs: list[str] = list(data.get(CONF_TRVS, []))
        self.window_sensors: list[str] = list(data.get(CONF_WINDOW_SENSORS, []))
        self.window_delay: float = float(data.get(CONF_WINDOW_DELAY, DEFAULT_WINDOW_DELAY))
        self.schedule: str | None = data.get(CONF_SCHEDULE) or None
        self.trv_heat: float = float(data.get(CONF_TRV_HEAT_TEMP, DEFAULT_TRV_HEAT_TEMP))
        self.trv_idle: float = float(data.get(CONF_TRV_IDLE_TEMP, DEFAULT_TRV_IDLE_TEMP))
        self.comfort_temp: float = float(data.get(CONF_COMFORT_TEMP, DEFAULT_COMFORT_TEMP))
        self.eco_temp: float = float(data.get(CONF_ECO_TEMP, DEFAULT_ECO_TEMP))
        self.away_temp: float = float(data.get(CONF_AWAY_TEMP, DEFAULT_AWAY_TEMP))
        hyst = data.get(CONF_HYSTERESIS)
        self.hysteresis: float | None = None if hyst in (None, "") else float(hyst)
        self.boost_minutes: float = float(data.get(CONF_BOOST_MINUTES, DEFAULT_BOOST_MINUTES))

        self.target: float = self.comfort_temp
        self.preset: str = PRESET_COMFORT if self.schedule else PRESET_NONE
        self.hvac_off = False
        self.window_open = False
        self.current: float | None = None
        self.demand = False
        self.reason = REASON_SATISFIED
        self.heating_seconds = 0.0
        self._acct_ts: datetime | None = None
        self._acct_on = False
        self._window_unsub: CALLBACK_TYPE | None = None
        self._boost_unsub: CALLBACK_TYPE | None = None
        self._pre_boost: tuple[str, float] | None = None

    @property
    def entity_ids(self) -> list[str]:
        """All entities this room listens to."""
        ids = [*self.temp_sensors, *self.trvs, *self.window_sensors]
        if self.schedule:
            ids.append(self.schedule)
        return ids

    @property
    def deficit(self) -> float | None:
        """Target minus current."""
        if self.current is None:
            return None
        return round(self.target - self.current, 2)

    @property
    def boost_active(self) -> bool:
        """Return True while boost preset is active."""
        return self.preset == PRESET_BOOST

    def heating_seconds_now(self, now: datetime | None = None) -> float:
        """Heating seconds today including the running segment."""
        total = self.heating_seconds
        if self._acct_on and self._acct_ts is not None:
            total += max(0.0, ((now or dt_util.utcnow()) - self._acct_ts).total_seconds())
        return total

    def _accumulate(self, now: datetime) -> None:
        if self._acct_on and self._acct_ts is not None:
            self.heating_seconds += max(0.0, (now - self._acct_ts).total_seconds())
        self._acct_ts = now

    def reset_daily(self, now: datetime) -> None:
        """Reset the daily counter."""
        self._accumulate(now)
        self.heating_seconds = 0.0

    # ----- user actions -----
    def restore(self, target: float | None, hvac_off: bool, preset: str | None) -> None:
        """Restore state from the previous run."""
        if target is not None:
            self.target = target
        self.hvac_off = hvac_off
        if preset in (PRESET_COMFORT, PRESET_ECO, PRESET_AWAY):
            self.set_preset(preset)
        elif preset == PRESET_NONE:
            self.preset = PRESET_NONE

    def set_target(self, target: float) -> None:
        """Set target manually (preset becomes none)."""
        self._cancel_boost()
        self.target = float(target)
        self.preset = PRESET_NONE

    def set_hvac_off(self, off: bool) -> None:
        """Turn the room on or off."""
        self.hvac_off = off

    def set_preset(self, preset: str) -> None:
        """Apply a preset."""
        if preset == PRESET_BOOST:
            self.start_boost()
            return
        self._cancel_boost()
        self.preset = preset
        if preset == PRESET_COMFORT:
            self.target = self.comfort_temp
        elif preset == PRESET_ECO:
            self.target = self.eco_temp
        elif preset == PRESET_AWAY:
            self.target = self.away_temp

    def start_boost(self) -> None:
        """Force demand on for boost_minutes."""
        if self.boost_active:
            return
        self._pre_boost = (self.preset, self.target)
        self.preset = PRESET_BOOST
        self._boost_unsub = async_call_later(
            self.hass, self.boost_minutes * 60, self._boost_expired
        )

    def end_boost(self) -> None:
        """End boost and revert to the previous preset."""
        if not self.boost_active:
            return
        self._cancel_boost()
        preset, target = self._pre_boost or (PRESET_NONE, self.target)
        self._pre_boost = None
        self.preset = preset
        self.target = target

    def _cancel_boost(self) -> None:
        if self._boost_unsub is not None:
            self._boost_unsub()
            self._boost_unsub = None

    @callback
    def _boost_expired(self, _now: datetime) -> None:
        self._boost_unsub = None
        self.end_boost()
        self.coordinator.async_evaluate()

    # ----- evaluation -----
    def _mean_temperature(self) -> float | None:
        values = []
        for entity_id in self.temp_sensors:
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            number = _valid_number(state.state)
            if number is not None:
                values.append(number)
        if not values:
            return None
        return round(sum(values) / len(values), 3)

    def _raw_window_open(self) -> bool:
        for entity_id in self.window_sensors:
            state = self.hass.states.get(entity_id)
            if state is not None and state.state == STATE_ON:
                return True
        return False

    def _update_window(self) -> None:
        if not self._raw_window_open():
            self.cancel_window_timer()
            self.window_open = False
        elif not self.window_open and self._window_unsub is None:
            if self.window_delay <= 0:
                self.window_open = True
            else:
                self._window_unsub = async_call_later(
                    self.hass, self.window_delay, self._window_timer
                )

    @callback
    def _window_timer(self, _now: datetime) -> None:
        self._window_unsub = None
        if self._raw_window_open():
            self.window_open = True
            self.coordinator.async_evaluate()

    def cancel_window_timer(self) -> None:
        """Cancel the pending window delay."""
        if self._window_unsub is not None:
            self._window_unsub()
            self._window_unsub = None

    def _apply_schedule(self) -> None:
        if not self.schedule or self.preset not in (PRESET_COMFORT, PRESET_ECO):
            return
        state = self.hass.states.get(self.schedule)
        if state is None or state.state not in (STATE_ON, STATE_OFF):
            return
        if state.state == STATE_ON:
            self.preset, self.target = PRESET_COMFORT, self.comfort_temp
        else:
            self.preset, self.target = PRESET_ECO, self.eco_temp

    def evaluate(self, now: datetime) -> None:
        """Recompute demand."""
        self._accumulate(now)
        self.current = self._mean_temperature()
        self._apply_schedule()
        self._update_window()
        hyst = (
            self.hysteresis if self.hysteresis is not None else self.coordinator.default_hysteresis
        )
        self.demand, self.reason = compute_demand(
            self.current,
            self.target,
            hyst,
            self.demand,
            self.hvac_off,
            self.window_open,
            self.boost_active,
        )
        self._acct_on = self.demand

    def desired_trv_temperature(self) -> float:
        """TRV setpoint for the current demand."""
        return trv_setpoint(self.demand, self.reason, self.target, self.trv_heat, self.trv_idle)

    def apply_trvs(self) -> None:
        """Send setpoints to TRVs that differ."""
        desired = self.desired_trv_temperature()
        for trv in self.trvs:
            self.coordinator.set_climate_temperature(trv, desired)

    def shutdown(self) -> None:
        """Cancel timers."""
        self.cancel_window_timer()
        self._cancel_boost()


class ThermoCoordinator:
    """Drive rooms and the boiler."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Create the coordinator."""
        self.hass = hass
        self.entry = entry
        self._conf = {**entry.data, **entry.options}
        self.rooms: dict[str, Room] = {
            sub.subentry_id: Room(self, sub)
            for sub in entry.subentries.values()
            if sub.subentry_type == SUBENTRY_ROOM
        }
        self._listeners: list[CALLBACK_TYPE] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._boiler_timer: CALLBACK_TYPE | None = None
        self._started = False
        self._stopped = False
        self.boiler_heating = False
        self.boiler_changed: datetime | None = None
        self.any_demand = False
        self.boiler_seconds = 0.0
        self._boiler_acct_ts: datetime | None = None

    # ----- config -----
    @property
    def boiler_climate(self) -> str | None:
        """Boiler climate entity id."""
        return self._conf.get(CONF_BOILER_CLIMATE) or None

    @property
    def boiler_heat_temp(self) -> float:
        """Boiler heat temperature."""
        return float(self._conf.get(CONF_BOILER_HEAT_TEMP, DEFAULT_BOILER_HEAT_TEMP))

    @property
    def boiler_idle_temp(self) -> float:
        """Boiler idle temperature."""
        return float(self._conf.get(CONF_BOILER_IDLE_TEMP, DEFAULT_BOILER_IDLE_TEMP))

    @property
    def min_on_s(self) -> float:
        """Minimum on time in seconds."""
        return float(self._conf.get(CONF_MIN_ON_MINUTES, DEFAULT_MIN_ON_MINUTES)) * 60

    @property
    def min_off_s(self) -> float:
        """Minimum off time in seconds."""
        return float(self._conf.get(CONF_MIN_OFF_MINUTES, DEFAULT_MIN_OFF_MINUTES)) * 60

    @property
    def default_hysteresis(self) -> float:
        """Default hysteresis."""
        return float(self._conf.get(CONF_DEFAULT_HYSTERESIS, DEFAULT_HYSTERESIS))

    # ----- listeners for entities -----
    @callback
    def async_add_listener(self, update_callback: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Register an entity update callback."""
        self._listeners.append(update_callback)

        @callback
        def remove() -> None:
            if update_callback in self._listeners:
                self._listeners.remove(update_callback)

        return remove

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    # ----- lifecycle -----
    @callback
    def async_start(self) -> None:
        """Subscribe to changes and evaluate once HA is running."""
        entities: set[str] = set()
        for room in self.rooms.values():
            entities.update(room.entity_ids)
        if entities:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, sorted(entities), self._handle_state_event
                )
            )
        self._unsubs.append(
            async_track_time_interval(
                self.hass,
                self._handle_interval,
                timedelta(minutes=SAFETY_INTERVAL_MINUTES),
            )
        )
        self._unsubs.append(
            async_track_time_change(self.hass, self._handle_midnight, hour=0, minute=0, second=0)
        )
        if self.hass.is_running:
            self._started = True
            self.async_evaluate()
        else:
            self._unsubs.append(
                self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self._handle_started)
            )

    @callback
    def async_stop(self) -> None:
        """Clean up everything."""
        self._stopped = True
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._boiler_timer is not None:
            self._boiler_timer()
            self._boiler_timer = None
        for room in self.rooms.values():
            room.shutdown()
        self._listeners.clear()

    @callback
    def _handle_started(self, _event: Event) -> None:
        self._started = True
        self.async_evaluate()

    @callback
    def _handle_state_event(self, _event: Event) -> None:
        self.async_evaluate()

    @callback
    def _handle_interval(self, _now: datetime) -> None:
        self.async_evaluate()

    @callback
    def _handle_midnight(self, now: datetime) -> None:
        now = dt_util.utcnow()
        for room in self.rooms.values():
            room.reset_daily(now)
        self._accumulate_boiler(now)
        self.boiler_seconds = 0.0
        self._notify()

    # ----- helpers -----
    def boiler_seconds_now(self, now: datetime | None = None) -> float:
        """Boiler on-time today."""
        total = self.boiler_seconds
        if self.boiler_heating and self._boiler_acct_ts is not None:
            total += max(0.0, ((now or dt_util.utcnow()) - self._boiler_acct_ts).total_seconds())
        return total

    def _accumulate_boiler(self, now: datetime) -> None:
        if self.boiler_heating and self._boiler_acct_ts is not None:
            self.boiler_seconds += max(0.0, (now - self._boiler_acct_ts).total_seconds())
        self._boiler_acct_ts = now

    @property
    def lockout_remaining(self) -> float:
        """Seconds until the boiler may change state again."""
        if self.boiler_changed is None:
            return 0.0
        since = (dt_util.utcnow() - self.boiler_changed).total_seconds()
        limit = self.min_on_s if self.boiler_heating else self.min_off_s
        return max(0.0, limit - since)

    @property
    def rooms_calling(self) -> list[Room]:
        """Rooms with demand."""
        return [room for room in self.rooms.values() if room.demand]

    def set_climate_temperature(self, entity_id: str, desired: float) -> None:
        """Call climate.set_temperature when the setpoint differs."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        current = _valid_number(state.attributes.get(ATTR_TEMPERATURE))
        if current is not None and abs(current - desired) <= SETPOINT_TOLERANCE:
            return
        self.hass.async_create_task(
            self.hass.services.async_call(
                "climate",
                "set_temperature",
                {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: desired},
                blocking=True,
            )
        )

    # ----- evaluation -----
    @callback
    def async_evaluate(self) -> None:
        """Evaluate all rooms and the boiler."""
        if self._stopped or not self._started:
            return
        now = dt_util.utcnow()
        for room in self.rooms.values():
            room.evaluate(now)
            room.apply_trvs()
        self.any_demand = any(room.demand for room in self.rooms.values())
        self._evaluate_boiler(now)
        self._notify()

    def _evaluate_boiler(self, now: datetime) -> None:
        if self._boiler_timer is not None:
            self._boiler_timer()
            self._boiler_timer = None
        since = (
            (now - self.boiler_changed).total_seconds()
            if self.boiler_changed is not None
            else _NEVER
        )
        action, wait = boiler_action(
            self.any_demand, self.boiler_heating, since, self.min_on_s, self.min_off_s
        )
        if action == "heat" and not self.boiler_heating:
            self._accumulate_boiler(now)
            self.boiler_heating = True
            self.boiler_changed = now
        elif action == "idle" and self.boiler_heating:
            self._accumulate_boiler(now)
            self.boiler_heating = False
            self.boiler_changed = now
        elif action == "wait":
            self._boiler_timer = async_call_later(self.hass, wait + 1, self._boiler_recheck)
        if self.boiler_climate:
            desired = self.boiler_heat_temp if self.boiler_heating else self.boiler_idle_temp
            self.set_climate_temperature(self.boiler_climate, desired)

    @callback
    def _boiler_recheck(self, _now: datetime) -> None:
        self._boiler_timer = None
        self.async_evaluate()


__all__ = ["REASON_OFF", "Room", "ThermoCoordinator"]
