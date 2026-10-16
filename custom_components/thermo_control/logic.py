"""Pure heating logic (no Home Assistant imports)."""

from __future__ import annotations

REASON_HEATING = "heating"
REASON_SATISFIED = "satisfied"
REASON_WINDOW = "window"
REASON_OFF = "off"
REASON_NO_SENSOR = "no_sensor"
REASON_BOOST = "boost"


def compute_demand(
    current: float | None,
    target: float,
    hysteresis: float,
    previous_demand: bool,
    hvac_off: bool,
    window_open: bool,
    boost: bool,
) -> tuple[bool, str]:
    """Return (demand, reason) for a room."""
    if hvac_off:
        return False, REASON_OFF
    if window_open:
        return False, REASON_WINDOW
    if boost:
        return True, REASON_BOOST
    if current is None:
        return False, REASON_NO_SENSOR
    if current >= target:
        return False, REASON_SATISFIED
    if current <= target - hysteresis:
        return True, REASON_HEATING
    if previous_demand:
        return True, REASON_HEATING
    return False, REASON_SATISFIED


def trv_setpoint(demand: bool, reason: str, target: float, heat: float, idle: float) -> float:
    """Return the temperature to command on a TRV."""
    if demand:
        return float(heat)
    if reason == REASON_SATISFIED:
        return float(target) + 1.0
    return float(idle)


def boiler_action(
    any_demand: bool,
    boiler_is_heating: bool,
    seconds_since_last_change: float,
    min_on_s: float,
    min_off_s: float,
) -> tuple[str, float]:
    """Decide boiler action: ("heat"|"idle"|"wait", wait_seconds)."""
    if any_demand:
        if boiler_is_heating:
            return "heat", 0.0
        if seconds_since_last_change >= min_off_s:
            return "heat", 0.0
        return "wait", min_off_s - seconds_since_last_change
    if not boiler_is_heating:
        return "idle", 0.0
    if seconds_since_last_change >= min_on_s:
        return "idle", 0.0
    return "wait", min_on_s - seconds_since_last_change
