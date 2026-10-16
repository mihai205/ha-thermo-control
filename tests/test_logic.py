"""Tests for pure logic."""

import pytest

from custom_components.thermo_control.logic import (
    boiler_action,
    compute_demand,
    trv_setpoint,
)


def cd(current=19.0, target=21.0, hyst=0.3, prev=False, off=False, window=False, boost=False):
    return compute_demand(current, target, hyst, prev, off, window, boost)


def test_off_wins_over_everything():
    assert cd(off=True, window=True, boost=True, current=10) == (False, "off")


def test_window_beats_boost():
    assert cd(window=True, boost=True) == (False, "window")


def test_boost_forces_demand_even_when_warm():
    assert cd(current=30, boost=True) == (True, "boost")


def test_no_sensor():
    assert cd(current=None) == (False, "no_sensor")
    assert cd(current=None, prev=True) == (False, "no_sensor")


def test_boost_without_sensor():
    assert cd(current=None, boost=True) == (True, "boost")


@pytest.mark.parametrize(
    ("current", "prev", "expected"),
    [
        (20.7, False, (True, "heating")),  # exactly target - hyst
        (20.6, False, (True, "heating")),
        (20.71, False, (False, "satisfied")),  # inside band, was idle
        (20.71, True, (True, "heating")),  # inside band, was heating
        (20.99, True, (True, "heating")),
        (21.0, True, (False, "satisfied")),  # exactly target
        (21.5, False, (False, "satisfied")),
    ],
)
def test_hysteresis_edges(current, prev, expected):
    assert cd(current=current, prev=prev) == expected


def test_zero_hysteresis():
    assert cd(current=21.0, hyst=0.0, prev=True) == (False, "satisfied")
    assert cd(current=21.1, hyst=0.0, prev=True) == (False, "satisfied")
    assert cd(current=20.9, hyst=0.0) == (True, "heating")


def test_trv_setpoint_demand():
    assert trv_setpoint(True, "heating", 21.0, 28.0, 16.5) == 28.0
    assert trv_setpoint(True, "boost", 21.0, 28.0, 16.5) == 28.0


def test_trv_setpoint_satisfied_keeps_decimal():
    result = trv_setpoint(False, "satisfied", 20.5, 28.0, 16.5)
    assert result == 21.5
    assert isinstance(result, float)


@pytest.mark.parametrize("reason", ["window", "off", "no_sensor"])
def test_trv_setpoint_idle(reason):
    assert trv_setpoint(False, reason, 21.0, 28.0, 16.5) == 16.5


def test_boiler_no_demand_off():
    assert boiler_action(False, False, 0, 300, 600) == ("idle", 0)


def test_boiler_demand_already_heating():
    assert boiler_action(True, True, 0, 300, 600) == ("heat", 0)


def test_boiler_turn_on_after_min_off():
    assert boiler_action(True, False, 600, 300, 600) == ("heat", 0)
    assert boiler_action(True, False, 1e9, 300, 600) == ("heat", 0)


def test_boiler_turn_on_blocked_waits_remaining():
    assert boiler_action(True, False, 100, 300, 600) == ("wait", 500)


def test_boiler_turn_off_after_min_on():
    assert boiler_action(False, True, 300, 300, 600) == ("idle", 0)


def test_boiler_turn_off_blocked_waits_remaining():
    assert boiler_action(False, True, 120, 300, 600) == ("wait", 180)


def test_boiler_zero_lockouts():
    assert boiler_action(True, False, 0, 0, 0) == ("heat", 0)
    assert boiler_action(False, True, 0, 0, 0) == ("idle", 0)
