# Anti-Cycling Climate

A HACS custom integration that applies the Anti-Cycling climate behavior to any Home Assistant `climate` entity exposing the required temperature attributes and one or more of the `heat`, `cool`, or `dry` HVAC modes.

## Features

- Configure one independent room/device per integration entry.
- Select a climate entity and a room temperature sensor in the UI.
- Get a native target-temperature slider (`number`) and an Anti-Cycling enable switch (`switch`).
- No manually-created helpers or YAML automation required. The hysteresis latch is maintained internally.

## Installation

1. In HACS, open **Integrations** → **⋮** → **Custom repositories**.
2. Add this GitHub repository URL and select **Integration** as the category.
3. Install **Anti-Cycling Climate** and restart Home Assistant.
4. Go to **Settings** → **Devices & services** → **Add integration** and search for **Anti-Cycling Climate**.
5. Select the climate entity and room-temperature sensor. Repeat the integration setup for each room/device.

## Compatibility

The selected climate entity must expose `current_temperature`, `temperature`, and at least one of `heat`, `cool`, or `dry` in its supported HVAC modes. The temperature sensor must have a numeric state. Entity selection is generic; no Midea-specific integration is required.

The default target-temperature slider range is 16–30 °C in 0.5 °C steps. These values are configurable during setup. Hysteresis settings can be changed later in the integration's **Configure** options. Defaults match the supplied automation: 1.2 °C above target, 17 °C setback while too warm, and a 2 °C offset in the normal heating range. The integration uses °C, matching the automation logic it replaces.

## Behavior

- **Heat:** at or below the target, set the climate target to the current climate temperature and clear the warm latch. At or above target + 1.2 °C, set the warm latch and command 17 °C. Otherwise, while the warm latch is clear, command the current temperature rounded down to a half degree minus 2 °C.
- **Cool / dry:** if the climate entity's current temperature is at or above the target, command the target; otherwise command the current temperature.
- **Off / other modes:** do nothing.
- The enable switch prevents control actions while off. The default is on.

## Development

The repository root is the HACS repository. Home Assistant loads the integration from `custom_components/anti_cycling_climate/`.
