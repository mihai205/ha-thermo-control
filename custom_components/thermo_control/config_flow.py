"""Config flow."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

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
    CONF_NAME,
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
    DOMAIN,
    SUBENTRY_ROOM,
)


def _num(low: float, high: float, step: float, unit: str | None = None):
    return NumberSelector(
        NumberSelectorConfig(
            min=low,
            max=high,
            step=step,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement=unit,
        )
    )


def _hub_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Optional(CONF_BOILER_CLIMATE): EntitySelector(
                EntitySelectorConfig(domain="climate")
            ),
            vol.Required(
                CONF_BOILER_HEAT_TEMP,
                default=defaults.get(CONF_BOILER_HEAT_TEMP, DEFAULT_BOILER_HEAT_TEMP),
            ): _num(5, 35, 0.5, "°C"),
            vol.Required(
                CONF_BOILER_IDLE_TEMP,
                default=defaults.get(CONF_BOILER_IDLE_TEMP, DEFAULT_BOILER_IDLE_TEMP),
            ): _num(5, 35, 0.5, "°C"),
            vol.Required(
                CONF_MIN_ON_MINUTES,
                default=defaults.get(CONF_MIN_ON_MINUTES, DEFAULT_MIN_ON_MINUTES),
            ): _num(0, 120, 1, "min"),
            vol.Required(
                CONF_MIN_OFF_MINUTES,
                default=defaults.get(CONF_MIN_OFF_MINUTES, DEFAULT_MIN_OFF_MINUTES),
            ): _num(0, 120, 1, "min"),
            vol.Required(
                CONF_DEFAULT_HYSTERESIS,
                default=defaults.get(CONF_DEFAULT_HYSTERESIS, DEFAULT_HYSTERESIS),
            ): _num(0, 5, 0.1, "°C"),
        }
    )


def _room_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME): TextSelector(),
            vol.Required(CONF_TEMP_SENSORS): EntitySelector(
                EntitySelectorConfig(domain="sensor", device_class="temperature", multiple=True)
            ),
            vol.Required(CONF_TRVS): EntitySelector(
                EntitySelectorConfig(domain="climate", multiple=True)
            ),
            vol.Optional(CONF_WINDOW_SENSORS): EntitySelector(
                EntitySelectorConfig(domain="binary_sensor", multiple=True)
            ),
            vol.Required(CONF_WINDOW_DELAY, default=DEFAULT_WINDOW_DELAY): _num(0, 600, 1, "s"),
            vol.Optional(CONF_SCHEDULE): EntitySelector(EntitySelectorConfig(domain="schedule")),
            vol.Required(CONF_TRV_HEAT_TEMP, default=DEFAULT_TRV_HEAT_TEMP): _num(5, 35, 0.5, "°C"),
            vol.Required(CONF_TRV_IDLE_TEMP, default=DEFAULT_TRV_IDLE_TEMP): _num(5, 35, 0.5, "°C"),
            vol.Required(CONF_COMFORT_TEMP, default=DEFAULT_COMFORT_TEMP): _num(5, 30, 0.5, "°C"),
            vol.Required(CONF_ECO_TEMP, default=DEFAULT_ECO_TEMP): _num(5, 30, 0.5, "°C"),
            vol.Required(CONF_AWAY_TEMP, default=DEFAULT_AWAY_TEMP): _num(5, 30, 0.5, "°C"),
            vol.Optional(CONF_HYSTERESIS): _num(0, 5, 0.1, "°C"),
            vol.Required(CONF_BOOST_MINUTES, default=DEFAULT_BOOST_MINUTES): _num(1, 480, 1, "min"),
        }
    )


class ThermoControlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Hub config flow."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Room subentries."""
        return {SUBENTRY_ROOM: RoomSubentryFlow}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Options flow."""
        return ThermoControlOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Create the hub."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="Thermo Control", data=user_input)
        return self.async_show_form(step_id="user", data_schema=_hub_schema())


class ThermoControlOptionsFlow(OptionsFlow):
    """Edit hub settings."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Edit options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = {**self.config_entry.data, **self.config_entry.options}
        schema = self.add_suggested_values_to_schema(_hub_schema(current), current)
        return self.async_show_form(step_id="init", data_schema=schema)


class RoomSubentryFlow(ConfigSubentryFlow):
    """Add or reconfigure a room."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Add a room."""
        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
        return self.async_show_form(step_id="user", data_schema=_room_schema())

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure a room."""
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                title=user_input[CONF_NAME],
                data=user_input,
            )
        schema = self.add_suggested_values_to_schema(_room_schema(), subentry.data)
        return self.async_show_form(step_id="reconfigure", data_schema=schema)
