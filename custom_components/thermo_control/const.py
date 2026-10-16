"""Constants for Thermo Control."""

from __future__ import annotations

DOMAIN = "thermo_control"
SUBENTRY_ROOM = "room"

# Hub options
CONF_BOILER_CLIMATE = "boiler_climate"
CONF_BOILER_HEAT_TEMP = "boiler_heat_temp"
CONF_BOILER_IDLE_TEMP = "boiler_idle_temp"
CONF_MIN_ON_MINUTES = "min_on_minutes"
CONF_MIN_OFF_MINUTES = "min_off_minutes"
CONF_DEFAULT_HYSTERESIS = "default_hysteresis"

DEFAULT_BOILER_HEAT_TEMP = 24.0
DEFAULT_BOILER_IDLE_TEMP = 15.0
DEFAULT_MIN_ON_MINUTES = 5
DEFAULT_MIN_OFF_MINUTES = 10
DEFAULT_HYSTERESIS = 0.3

# Room settings
CONF_NAME = "name"
CONF_TEMP_SENSORS = "temp_sensors"
CONF_TRVS = "trvs"
CONF_WINDOW_SENSORS = "window_sensors"
CONF_WINDOW_DELAY = "window_delay_seconds"
CONF_SCHEDULE = "schedule"
CONF_TRV_HEAT_TEMP = "trv_heat_temp"
CONF_TRV_IDLE_TEMP = "trv_idle_temp"
CONF_COMFORT_TEMP = "comfort_temp"
CONF_ECO_TEMP = "eco_temp"
CONF_AWAY_TEMP = "away_temp"
CONF_HYSTERESIS = "hysteresis"
CONF_BOOST_MINUTES = "boost_minutes"

DEFAULT_WINDOW_DELAY = 30
DEFAULT_TRV_HEAT_TEMP = 28.0
DEFAULT_TRV_IDLE_TEMP = 16.5
DEFAULT_COMFORT_TEMP = 21.0
DEFAULT_ECO_TEMP = 18.0
DEFAULT_AWAY_TEMP = 16.0
DEFAULT_BOOST_MINUTES = 30

# Presets
PRESET_COMFORT = "comfort"
PRESET_ECO = "eco"
PRESET_AWAY = "away"
PRESET_BOOST = "boost"
PRESET_NONE = "none"

# Demand reasons
REASON_HEATING = "heating"
REASON_SATISFIED = "satisfied"
REASON_WINDOW = "window"
REASON_OFF = "off"
REASON_NO_SENSOR = "no_sensor"
REASON_BOOST = "boost"
REASONS = [
    REASON_HEATING,
    REASON_SATISFIED,
    REASON_WINDOW,
    REASON_OFF,
    REASON_NO_SENSOR,
    REASON_BOOST,
]

SAFETY_INTERVAL_MINUTES = 5
SETPOINT_TOLERANCE = 0.05
