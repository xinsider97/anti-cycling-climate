# Anti-Cycling Climate

A HACS custom integration that applies the Anti-Cycling climate behavior to any Home Assistant `climate` entity exposing the required temperature attributes and one or more of the `heat`, `cool`, or `dry` HVAC modes.

## Features

- Configure one independent room/device per integration entry.
- Select a climate entity and a room temperature sensor in the UI.
- Get a virtual climate entity that mirrors the source climate's HVAC modes, target, fan, preset, swing, and on/off controls where supported, plus an Anti-Cycling enable switch (`switch`).
- No manually-created helpers or YAML automation required. The hysteresis latch is maintained internally.

Home Assistant registers devices per config entry. Because the selected climate entity belongs to its source integration (for example ESPHome) and Anti-Cycling Climate has its own config entry, Home Assistant shows a separate **service device** named `<climate name> Anti-Cycling`. Its virtual climate shows the requested target (for example 22 °C), while the source climate can temporarily receive a different anti-cycling setpoint (for example 17 °C).

## Installation

1. In HACS, open **Integrations** → **⋮** → **Custom repositories**.
2. Add this GitHub repository URL and select **Integration** as the category.
3. Install **Anti-Cycling Climate** and restart Home Assistant.
4. Go to **Settings** → **Devices & services** → **Add integration** and search for **Anti-Cycling Climate**.
5. Select the climate entity and room-temperature sensor. Repeat the integration setup for each room/device.

## Compatibility

The selected climate entity must expose `current_temperature`, `temperature`, and at least one of `heat`, `cool`, or `dry` in its supported HVAC modes. The temperature sensor must have a numeric state. Entity selection is generic; no Midea-specific integration is required.

The virtual climate automatically uses the selected climate entity's `min_temp`, `max_temp`, and `target_temp_step` attributes. Commands are clamped to the climate entity's allowed range and rounded to its supported temperature increment. Hysteresis settings can be changed during setup and later in the integration's **Configure** options. Defaults match the supplied automation: 1.2 °C above target, 17 °C setback while too warm (clamped to the device limits when necessary), and a 2 °C offset in the normal heating range. Defaults are converted for climate entities using °F; the virtual climate follows the selected climate entity's native temperature unit.

## Behavior

- **Heat:** at or below the target, set the climate target to the current climate temperature and clear the warm latch. At or above target + 1.2 °C, set the warm latch and command 17 °C. Otherwise, while the warm latch is clear, command the current temperature rounded down to a half degree minus 2 °C.
- **Other HVAC modes:** the requested target is passed straight through to the physical climate.
- When the enable switch is off, the requested target is passed straight through in every mode.
- Supported HVAC modes, fan modes, presets, swing modes, and on/off controls are mirrored from the selected climate entity.
- The enable switch defaults to on.

## Development

The repository root is the HACS repository. Home Assistant loads the integration from `custom_components/anti_cycling_climate/`.
