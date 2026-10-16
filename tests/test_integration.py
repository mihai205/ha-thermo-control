"""Integration tests."""

from datetime import timedelta

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.thermo_control.const import DOMAIN

HUB = {
    "boiler_climate": "climate.boiler",
    "boiler_heat_temp": 24,
    "boiler_idle_temp": 15,
    "min_on_minutes": 5,
    "min_off_minutes": 10,
    "default_hysteresis": 0.3,
}
ROOM = {
    "name": "Living",
    "temp_sensors": ["sensor.t1", "sensor.t2"],
    "trvs": ["climate.trv1"],
    "window_sensors": ["binary_sensor.win"],
    "window_delay_seconds": 30,
    "trv_heat_temp": 28,
    "trv_idle_temp": 16.5,
    "comfort_temp": 21,
    "eco_temp": 18,
    "away_temp": 16,
    "boost_minutes": 30,
}


def set_temps(hass, t1, t2=None):
    hass.states.async_set("sensor.t1", str(t1), {"device_class": "temperature"})
    hass.states.async_set(
        "sensor.t2", "unavailable" if t2 is None else str(t2), {"device_class": "temperature"}
    )


async def setup(hass, hub=None, room=None):
    await async_setup_component(hass, "climate", {})
    calls = async_mock_service(hass, "climate", "set_temperature")
    hass.states.async_set("climate.trv1", "heat", {"temperature": 20})
    hass.states.async_set("climate.boiler", "heat", {"temperature": 15})
    hass.states.async_set("binary_sensor.win", "off")
    set_temps(hass, 19.0)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=hub or HUB,
        unique_id=DOMAIN,
        subentries_data=[
            ConfigSubentryData(
                subentry_type="room",
                title="Living",
                subentry_id="room1",
                unique_id=None,
                data=room or ROOM,
            )
        ],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, calls


def by_entity(calls, entity_id):
    return [c.data["temperature"] for c in calls if c.data["entity_id"] == entity_id]


async def tick(hass, freezer, seconds):
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()


async def test_demand_drives_trv_and_boiler(hass: HomeAssistant, freezer):
    entry, calls = await setup(hass)
    # mean ignores unavailable t2: 19.0 <= 21 - 0.3 -> demand
    state = hass.states.get("climate.living")
    assert state.attributes["current_temperature"] == 19.0
    assert state.attributes["demand"] is True
    assert state.attributes["hvac_action"] == "heating"
    assert hass.states.get("binary_sensor.living_heat_demand").state == "on"
    assert hass.states.get("sensor.living_demand_reason").state == "heating"
    assert float(hass.states.get("sensor.living_temperature_deficit").state) == 2.0
    assert by_entity(calls, "climate.trv1") == [28.0]
    assert by_entity(calls, "climate.boiler") == [24.0]
    assert hass.states.get("binary_sensor.thermo_control_boiler_demand").state == "on"
    assert hass.states.get("sensor.thermo_control_rooms_calling").state == "1"

    # TRV already at desired -> no repeat call
    hass.states.async_set("climate.trv1", "heat", {"temperature": 28})
    hass.states.async_set("climate.boiler", "heat", {"temperature": 24})
    calls.clear()
    set_temps(hass, 19.5, 19.5)
    await hass.async_block_till_done()
    assert calls == []

    # satisfied -> TRV target + 1; boiler held by min_on
    set_temps(hass, 21.5, 21.5)
    await hass.async_block_till_done()
    assert set(by_entity(calls, "climate.trv1")) == {22.0}
    assert by_entity(calls, "climate.boiler") == []
    assert hass.states.get("sensor.living_demand_reason").state == "satisfied"

    await tick(hass, freezer, 301)
    assert set(by_entity(calls, "climate.boiler")) == {15.0}


async def test_window_delay(hass: HomeAssistant, freezer):
    _entry, calls = await setup(hass)
    calls.clear()
    hass.states.async_set("binary_sensor.win", "on")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.living_demand_reason").state == "heating"
    await tick(hass, freezer, 31)
    assert hass.states.get("sensor.living_demand_reason").state == "window"
    assert hass.states.get("climate.living").attributes["window_open"] is True
    assert 16.5 in by_entity(calls, "climate.trv1")
    # closing is immediate
    hass.states.async_set("binary_sensor.win", "off")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.living_demand_reason").state == "heating"


async def test_window_closed_before_delay(hass: HomeAssistant, freezer):
    await setup(hass)
    hass.states.async_set("binary_sensor.win", "on")
    await hass.async_block_till_done()
    await tick(hass, freezer, 10)
    hass.states.async_set("binary_sensor.win", "off")
    await hass.async_block_till_done()
    await tick(hass, freezer, 60)
    assert hass.states.get("sensor.living_demand_reason").state == "heating"


async def test_deferred_boiler_heat_after_lockout(hass: HomeAssistant, freezer):
    _entry, calls = await setup(hass)
    assert by_entity(calls, "climate.boiler") == [24.0]
    hass.states.async_set("climate.boiler", "heat", {"temperature": 24})
    # satisfy, wait past min_on so boiler goes idle
    set_temps(hass, 22.0)
    await hass.async_block_till_done()
    await tick(hass, freezer, 301)
    assert by_entity(calls, "climate.boiler")[-1] == 15.0
    hass.states.async_set("climate.boiler", "heat", {"temperature": 15})
    calls.clear()
    # demand returns inside min_off: must wait, then fire without new events
    set_temps(hass, 18.0)
    await hass.async_block_till_done()
    assert by_entity(calls, "climate.boiler") == []
    assert float(hass.states.get("sensor.thermo_control_boiler_lockout_remaining").state) > 0
    await tick(hass, freezer, 200)
    assert by_entity(calls, "climate.boiler") == []
    await tick(hass, freezer, 400)
    assert by_entity(calls, "climate.boiler") == [24.0]


async def test_no_boiler_configured(hass: HomeAssistant):
    hub = {k: v for k, v in HUB.items() if k != "boiler_climate"}
    _entry, calls = await setup(hass, hub=hub)
    assert by_entity(calls, "climate.boiler") == []
    assert by_entity(calls, "climate.trv1") == [28.0]


async def test_boost_switch_and_revert(hass: HomeAssistant, freezer):
    await setup(hass)
    set_temps(hass, 23.0)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.living_demand_reason").state == "satisfied"
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.living_boost"}, blocking=True
    )
    assert hass.states.get("sensor.living_demand_reason").state == "boost"
    assert hass.states.get("climate.living").attributes["preset_mode"] == "boost"
    await tick(hass, freezer, 31 * 60)
    assert hass.states.get("switch.living_boost").state == "off"
    assert hass.states.get("sensor.living_demand_reason").state == "satisfied"
    assert hass.states.get("climate.living").attributes["preset_mode"] == "none"


async def test_hvac_off_and_presets(hass: HomeAssistant):
    await setup(hass)
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.living", "preset_mode": "eco"},
        blocking=True,
    )
    attrs = hass.states.get("climate.living").attributes
    assert attrs["temperature"] == 18
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.living", "hvac_mode": "off"},
        blocking=True,
    )
    assert hass.states.get("climate.living").state == "off"
    assert hass.states.get("sensor.living_demand_reason").state == "off"


async def test_schedule_drives_preset(hass: HomeAssistant):
    hass.states.async_set("schedule.heat", "on")
    await setup(hass, room={**ROOM, "schedule": "schedule.heat"})
    attrs = hass.states.get("climate.living").attributes
    assert attrs["preset_mode"] == "comfort"
    assert attrs["temperature"] == 21
    hass.states.async_set("schedule.heat", "off")
    await hass.async_block_till_done()
    attrs = hass.states.get("climate.living").attributes
    assert attrs["preset_mode"] == "eco"
    assert attrs["temperature"] == 18
    # manual target disables auto
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    entry.runtime_data.rooms["room1"].set_target(23)
    entry.runtime_data.async_evaluate()
    hass.states.async_set("schedule.heat", "on")
    await hass.async_block_till_done()
    attrs = hass.states.get("climate.living").attributes
    assert attrs["preset_mode"] == "none"
    assert attrs["temperature"] == 23


async def test_reload_on_subentry_change_and_unload(hass: HomeAssistant):
    entry, _calls = await setup(hass)
    hass.config_entries.async_update_subentry(
        entry, entry.subentries["room1"], data={**ROOM, "comfort_temp": 22}
    )
    await hass.async_block_till_done()
    assert entry.runtime_data.rooms["room1"].comfort_temp == 22
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_diagnostics(hass: HomeAssistant):
    from custom_components.thermo_control.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    entry, _ = await setup(hass)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["rooms"]["room1"]["name"] == "Living"
