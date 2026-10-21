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
    DEFAULT_TARGET_MAX,
    DEFAULT_TARGET_MIN,
    DEFAULT_TARGET_STEP,
    DEFAULT_WARM_MARGIN,
    DOMAIN,
)


class AntiCyclingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a climate entity and its room sensor."""

    VERSION = 1

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
            elif float(user_input[CONF_TARGET_MIN]) >= float(user_input[CONF_TARGET_MAX]):
                errors["base"] = "invalid_range"
            else:
                await self.async_set_unique_id(f"{climate_entity}:{sensor.entity_id}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=climate.attributes.get("friendly_name", climate_entity),
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_CLIMATE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate")
                ),
                vol.Required(CONF_SENSOR_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_TARGET_MIN, default=DEFAULT_TARGET_MIN): vol.Coerce(float),
                vol.Optional(CONF_TARGET_MAX, default=DEFAULT_TARGET_MAX): vol.Coerce(float),
                vol.Optional(CONF_TARGET_STEP, default=DEFAULT_TARGET_STEP): vol.All(
                    vol.Coerce(float), vol.Range(min=0.1, max=5)
                ),
                vol.Optional(CONF_WARM_MARGIN, default=DEFAULT_WARM_MARGIN): vol.All(
                    vol.Coerce(float), vol.Range(min=0.1, max=10)
                ),
                vol.Optional(CONF_COOLING_SETBACK, default=DEFAULT_COOLING_SETBACK): vol.All(
                    vol.Coerce(float), vol.Range(min=5, max=35)
                ),
                vol.Optional(CONF_HEAT_OFFSET, default=DEFAULT_HEAT_OFFSET): vol.All(
                    vol.Coerce(float), vol.Range(min=0, max=10)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return an options flow for hysteresis settings."""
        return AntiCyclingOptionsFlow(config_entry)


class AntiCyclingOptionsFlow(config_entries.OptionsFlow):
    """Edit hysteresis values after setup."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Show hysteresis settings."""
        if user_input is not None:
            return self.async_create_entry(
                title="", data={**self.config_entry.options, **user_input}
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_WARM_MARGIN,
                    default=self.config_entry.options.get(
                        CONF_WARM_MARGIN, self.config_entry.data[CONF_WARM_MARGIN]
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=10)),
                vol.Required(
                    CONF_COOLING_SETBACK,
                    default=self.config_entry.options.get(
                        CONF_COOLING_SETBACK, self.config_entry.data[CONF_COOLING_SETBACK]
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=5, max=35)),
                vol.Required(
                    CONF_HEAT_OFFSET,
                    default=self.config_entry.options.get(
                        CONF_HEAT_OFFSET, self.config_entry.data[CONF_HEAT_OFFSET]
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=10)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
