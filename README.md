# Thermo Control

Home Assistant custom integration for multi-room heating with thermostatic radiator valves (TRVs) and a boiler.

## Features

- Per-room virtual thermostat climate entity that averages multiple temperature sensors
- Hysteresis-based heat demand per room
- Window detection with configurable delay (no demand while a window is open)
- Presets: comfort, eco, away, boost
- Optional Schedule helper that switches between comfort and eco
- Timed boost switch
- Boiler control with minimum on/off times (anti-short-cycle): demand is deferred rather than dropped
- Diagnostic sensors: demand reason, deficit, heating time today, rooms calling for heat, boiler lockout remaining, boiler on-time today
- Restores state after a Home Assistant restart

## Installation

### HACS

1. Open HACS → Custom repositories.
2. Add `https://git.moweb.ro/moweb/ha-thermo-control` with category **Integration**.
3. Install **Thermo Control** and restart Home Assistant.

### Manual

1. Copy `custom_components/thermo_control` to `/config/custom_components/`.
2. Restart Home Assistant.

## Configuration

1. Go to **Settings → Devices & services → Add integration** and choose **Thermo Control**.
2. Configure the hub options:
   - Boiler climate entity
   - Heat and idle temperatures
   - Minimum on and off times
   - Hysteresis
3. Add rooms with **Add room** (a subentry for each room):
   - Temperature sensors
   - TRVs
   - Window sensors and window delay
   - Optional Schedule helper
   - TRV heat and idle temperatures
   - Preset temperatures
   - Hysteresis
   - Boost duration in minutes

## How it works

**Room demand rules**

- Room is off or a window is open: no demand.
- Boost active: demand.
- Temperature ≤ target − hysteresis: demand.
- Temperature ≥ target: no demand.
- In between: keeps the previous demand state.

**TRV setpoint**

- Room has demand: TRV set to the heat temperature.
- Room satisfied: TRV set to target + 1.
- Otherwise: TRV set to the idle temperature.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install pytest-homeassistant-custom-component ruff
pytest
```
