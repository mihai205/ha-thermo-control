"""Config flow tests."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.thermo_control.const import DOMAIN


async def test_hub_flow(hass: HomeAssistant):
    with patch("custom_components.thermo_control.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "boiler_climate": "climate.boiler",
                "boiler_heat_temp": 25,
                "boiler_idle_temp": 15,
                "min_on_minutes": 5,
                "min_off_minutes": 10,
                "default_hysteresis": 0.3,
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["boiler_climate"] == "climate.boiler"

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.ABORT


async def test_hub_flow_without_boiler(hass: HomeAssistant):
    with patch("custom_components.thermo_control.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "boiler_heat_temp": 24,
                "boiler_idle_temp": 15,
                "min_on_minutes": 5,
                "min_off_minutes": 10,
                "default_hysteresis": 0.3,
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "boiler_climate" not in result["data"]


async def test_options_flow(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "boiler_heat_temp": 24,
            "boiler_idle_temp": 15,
            "min_on_minutes": 5,
            "min_off_minutes": 10,
            "default_hysteresis": 0.3,
        },
    )
    entry.add_to_hass(hass)
    with patch("custom_components.thermo_control.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "boiler_heat_temp": 26,
                "boiler_idle_temp": 14,
                "min_on_minutes": 3,
                "min_off_minutes": 8,
                "default_hysteresis": 0.5,
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["boiler_heat_temp"] == 26


ROOM_INPUT = {
    "name": "Living",
    "temp_sensors": ["sensor.t1"],
    "trvs": ["climate.trv1"],
    "window_delay_seconds": 30,
    "trv_heat_temp": 28,
    "trv_idle_temp": 16.5,
    "comfort_temp": 21,
    "eco_temp": 18,
    "away_temp": 16,
    "boost_minutes": 30,
}


async def test_room_subentry_create_and_reconfigure(hass: HomeAssistant):
    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    with patch("custom_components.thermo_control.async_setup_entry", return_value=True):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "room"), context={"source": "user"}
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], ROOM_INPUT)
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert len(entry.subentries) == 1
        subentry = next(iter(entry.subentries.values()))
        assert subentry.title == "Living"
        assert subentry.data["trvs"] == ["climate.trv1"]

        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "room"),
            context={"source": "reconfigure", "subentry_id": subentry.subentry_id},
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {**ROOM_INPUT, "comfort_temp": 22}
        )
        assert result["type"] is FlowResultType.ABORT
        assert entry.subentries[subentry.subentry_id].data["comfort_temp"] == 22
