"""Virtual climate entity controlled by the Anti-Cycling algorithm."""

from __future__ import annotations

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_conversion import TemperatureConverter

from . import AntiCyclingRuntime, async_set_target, device_info_for_entry


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the virtual climate entity."""
    entity = AntiCyclingClimate(hass, entry)
    runtime: AntiCyclingRuntime = hass.data[entry.domain][entry.entry_id]
    runtime.virtual_climate = entity
    async_add_entities([entity])


class AntiCyclingClimate(ClimateEntity):
    """Present the requested temperature while controlling the physical climate."""

    _attr_has_entity_name = False
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize a virtual thermostat for one climate entity."""
        self.hass = hass
        self.entry = entry
        self._runtime: AntiCyclingRuntime = hass.data[entry.domain][entry.entry_id]
        self._attr_unique_id = f"{entry.entry_id}_climate"
        self._attr_name = f"{entry.title} (Anti-Cycling)"
        self._attr_device_info = device_info_for_entry(entry)
        climate = hass.states.get(self._runtime.climate_entity)
        source_modes = climate.attributes.get("hvac_modes", []) if climate else []
        self._attr_hvac_modes = [HVACMode(mode) for mode in source_modes]
        self._attr_hvac_modes = [
            mode
            for mode in self._attr_hvac_modes
            if mode in (HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.DRY)
        ]
        self._attr_min_temp = self._runtime.target_min
        self._attr_max_temp = self._runtime.target_max
        self._attr_target_temperature_step = self._runtime.target_temp_step
        self._attr_native_temperature_unit = self._runtime.temperature_unit
        self._attr_native_target_temperature = self._runtime.target

    @property
    def native_current_temperature(self) -> float | None:
        """Return room temperature converted to the climate entity's unit."""
        sensor = self.hass.states.get(self._runtime.sensor_entity)
        if sensor is None:
            return None
        try:
            temperature = float(sensor.state)
            sensor_unit = sensor.attributes.get(
                "unit_of_measurement", self._runtime.temperature_unit
            )
            if sensor_unit != self._runtime.temperature_unit:
                temperature = TemperatureConverter.convert(
                    temperature, sensor_unit, self._runtime.temperature_unit
                )
            return temperature
        except (TypeError, ValueError):
            return None

    @property
    def native_target_temperature(self) -> float:
        """Expose the user's requested target, never the temporary device setpoint."""
        return self._runtime.target

    @property
    def available(self) -> bool:
        """Be unavailable when the physical climate device is unavailable."""
        climate = self.hass.states.get(self._runtime.climate_entity)
        return climate is not None and climate.state not in ("unknown", "unavailable")

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Mirror the physical climate's current HVAC mode."""
        climate = self.hass.states.get(self._runtime.climate_entity)
        if climate is None:
            return None
        try:
            return HVACMode(climate.state)
        except ValueError:
            return None

    @property
    def hvac_action(self) -> HVACAction | None:
        """Mirror the physical climate's current action when available."""
        climate = self.hass.states.get(self._runtime.climate_entity)
        action = climate.attributes.get("hvac_action") if climate else None
        if action is None:
            return None
        try:
            return HVACAction(action)
        except ValueError:
            return None

    async def async_set_temperature(self, **kwargs) -> None:
        """Update the requested target while keeping the virtual climate stable."""
        temperature = kwargs.get("temperature")
        if temperature is None:
            return
        self._attr_native_target_temperature = float(temperature)
        await async_set_target(self.hass, self.entry, float(temperature))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Apply the selected HVAC mode to the physical climate entity."""
        if hvac_mode not in self._attr_hvac_modes:
            return
        await self.hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {
                "entity_id": self._runtime.climate_entity,
                "hvac_mode": hvac_mode.value,
            },
            blocking=False,
        )
