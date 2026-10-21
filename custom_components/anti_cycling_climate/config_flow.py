"""Config flow for Anti-Cycling Climate."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CLIMATE_ENTITY,
    CONF_COOLING_SETBACK,
    CONF_HEAT_OFFSET,
    CONF_SENSOR_ENTITY,
    CONF_TARGET_MAX,
    CONF_TARGET_MIN,
    CONF_TARGET_STEP,
    CONF_WARM_MARGIN,
    DEFAULT_COOLING_SETBACK,
    DEFAULT_HEAT_OFFSET,
    DEFAULT_TARGET_STEP,
    DEFAULT_WARM_MARGIN,
    DOMAIN,
)


class AntiCyclingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a climate entity and its room sensor."""

    VERSION = 1

    def __init__(self):
        """Initialize pending selection data."""
        self._user_data = {}

    async def async_step_user(self, user_input=None):
        """Collect entity selection and slider range."""
        errors = {}
        if user_input is not None:
            climate_entity = user_input[CONF_CLIMATE_ENTITY]
            climate = self.hass.states.get(climate_entity)
            sensor = self.hass.states.get(user_input[CONF_SENSOR_ENTITY])
            if climate is None or climate.domain != "climate":
                errors["base"] = "invalid_climate"
            elif not all(
                attr in climate.attributes
                for attr in ("current_temperature", "temperature", "hvac_modes")
            ) or not {"heat", "cool", "dry"}.intersection(
                climate.attributes.get("hvac_modes", [])
            ):
                errors["base"] = "unsupported_climate"
            elif sensor is None or sensor.domain != "sensor":
                errors["base"] = "invalid_sensor"
            elif not _valid_temperature_bounds(climate.attributes):
                errors["base"] = "missing_temperature_limits"
            else:
                self._user_data = user_input
                return await self.async_step_settings()

        schema = vol.Schema(
            {
                vol.Required(CONF_CLIMATE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate")
                ),
                vol.Required(CONF_SENSOR_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_settings(self, user_input=None):
        """Configure hysteresis within the selected climate's temperature limits."""
        climate = self.hass.states.get(self._user_data[CONF_CLIMATE_ENTITY])
        minimum = float(climate.attributes["min_temp"])
        maximum = float(climate.attributes["max_temp"])
        step = float(climate.attributes.get("target_temp_step", DEFAULT_TARGET_STEP))
        errors = {}

        if user_input is not None:
            setback = float(user_input[CONF_COOLING_SETBACK])
            if not minimum <= setback <= maximum:
                errors["base"] = "setback_out_of_range"
            else:
                data = {
                    **self._user_data,
                    **user_input,
                    CONF_TARGET_MIN: minimum,
                    CONF_TARGET_MAX: maximum,
                    CONF_TARGET_STEP: step,
                }
                await self.async_set_unique_id(
                    f"{self._user_data[CONF_CLIMATE_ENTITY]}:{self._user_data[CONF_SENSOR_ENTITY]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=climate.attributes.get(
                        "friendly_name", self._user_data[CONF_CLIMATE_ENTITY]
                    ),
                    data=data,
                )

        default_setback = min(max(DEFAULT_COOLING_SETBACK, minimum), maximum)
        schema = vol.Schema(
            {
                vol.Required(CONF_WARM_MARGIN, default=DEFAULT_WARM_MARGIN): vol.All(
                    vol.Coerce(float), vol.Range(min=0.1, max=10)
                ),
                vol.Required(CONF_COOLING_SETBACK, default=default_setback): vol.All(
                    vol.Coerce(float), vol.Range(min=minimum, max=maximum)
                ),
                vol.Required(CONF_HEAT_OFFSET, default=DEFAULT_HEAT_OFFSET): vol.All(
                    vol.Coerce(float), vol.Range(min=0, max=10)
                ),
            }
        )
        return self.async_show_form(
            step_id="settings", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return an options flow for hysteresis settings."""
        return AntiCyclingOptionsFlow(config_entry)


class AntiCyclingOptionsFlow(config_entries.OptionsFlow):
    """Edit hysteresis values after setup."""

    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Show hysteresis settings."""
        if user_input is not None:
            return self.async_create_entry(
                title="", data={**self._config_entry.options, **user_input}
            )

        minimum = float(self._config_entry.data[CONF_TARGET_MIN])
        maximum = float(self._config_entry.data[CONF_TARGET_MAX])
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_WARM_MARGIN,
                    default=self._config_entry.options.get(
                        CONF_WARM_MARGIN, self._config_entry.data[CONF_WARM_MARGIN]
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=10)),
                vol.Required(
                    CONF_COOLING_SETBACK,
                    default=self._config_entry.options.get(
                        CONF_COOLING_SETBACK, self._config_entry.data[CONF_COOLING_SETBACK]
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=minimum, max=maximum)),
                vol.Required(
                    CONF_HEAT_OFFSET,
                    default=self._config_entry.options.get(
                        CONF_HEAT_OFFSET, self._config_entry.data[CONF_HEAT_OFFSET]
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=10)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


def _valid_temperature_bounds(attributes):
    """Return whether the climate entity advertises usable setpoint limits."""
    try:
        return (
            float(attributes["min_temp"]) < float(attributes["max_temp"])
            and float(attributes.get("target_temp_step", DEFAULT_TARGET_STEP)) > 0
        )
    except (KeyError, TypeError, ValueError):
        return False
