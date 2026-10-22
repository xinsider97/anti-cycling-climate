"""Virtual climate entity controlled by the Anti-Cycling algorithm."""

from __future__ import annotations

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_conversion import TemperatureConverter

from . import AntiCyclingRuntime, async_set_target, device_info_for_entry

_PASSTHROUGH_FEATURES = (
    ClimateEntityFeature.FAN_MODE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.SWING_MODE
    | ClimateEntityFeature.SWING_HORIZONTAL_MODE
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TURN_OFF
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the virtual climate entity."""
    entity = AntiCyclingClimate(hass, entry)
    runtime: AntiCyclingRuntime = hass.data[entry.domain][entry.entry_id]
    runtime.virtual_climate = entity
    async_add_entities([entity])


class AntiCyclingClimate(ClimateEntity):
    """Mirror the source climate and intercept only its heating setpoint."""

    _attr_has_entity_name = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize a virtual thermostat for one climate entity."""
        self.hass = hass
        self.entry = entry
        self._runtime: AntiCyclingRuntime = hass.data[entry.domain][entry.entry_id]
        self._attr_unique_id = f"{entry.entry_id}_climate"
        self._attr_name = f"{entry.title} (Anti-Cycling)"
        self._attr_device_info = device_info_for_entry(entry)
        self._attr_min_temp = self._runtime.target_min
        self._attr_max_temp = self._runtime.target_max
        self._attr_target_temperature_step = self._runtime.target_temp_step
        # Keep both APIs populated while supported Home Assistant versions
        # transition climate temperature properties to their native_* names.
        self._attr_temperature_unit = self._runtime.temperature_unit
        self._attr_native_temperature_unit = self._runtime.temperature_unit
        self._attr_temperature = self._runtime.target
        self._attr_native_target_temperature = self._runtime.target

    def _source_state(self) -> State | None:
        """Return the latest state of the physical climate entity."""
        return self.hass.states.get(self._runtime.climate_entity)

    @property
    def available(self) -> bool:
        """Be unavailable when the physical climate device is unavailable."""
        climate = self._source_state()
        return climate is not None and climate.state not in ("unknown", "unavailable")

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Mirror every HVAC mode currently exposed by the physical climate."""
        climate = self._source_state()
        if climate is None:
            return []
        modes = []
        for mode in climate.attributes.get("hvac_modes", []):
            try:
                modes.append(HVACMode(mode))
            except ValueError:
                continue
        return modes

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Mirror the physical climate's current HVAC mode."""
        climate = self._source_state()
        if climate is None:
            return None
        try:
            return HVACMode(climate.state)
        except ValueError:
            return None

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Expose target-temperature and supported source controls."""
        climate = self._source_state()
        source_features = (
            ClimateEntityFeature(climate.attributes.get("supported_features", 0))
            if climate is not None
            else ClimateEntityFeature(0)
        )
        return ClimateEntityFeature.TARGET_TEMPERATURE | (
            source_features & _PASSTHROUGH_FEATURES
        )

    @property
    def min_temp(self) -> float:
        """Mirror the source climate's current minimum target."""
        climate = self._source_state()
        if climate is None:
            return self._runtime.target_min
        return float(climate.attributes.get("min_temp", self._runtime.target_min))

    @property
    def max_temp(self) -> float:
        """Mirror the source climate's current maximum target."""
        climate = self._source_state()
        if climate is None:
            return self._runtime.target_max
        return float(climate.attributes.get("max_temp", self._runtime.target_max))

    @property
    def target_temperature_step(self) -> float:
        """Mirror the source climate's setpoint increment."""
        climate = self._source_state()
        if climate is None:
            return self._runtime.target_temp_step
        return float(
            climate.attributes.get("target_temp_step", self._runtime.target_temp_step)
        )

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
    def current_temperature(self) -> float | None:
        """Legacy climate property for Home Assistant compatibility."""
        return self.native_current_temperature

    @property
    def native_target_temperature(self) -> float:
        """Expose the user's requested target, never the temporary device setpoint."""
        return self._runtime.target

    @property
    def target_temperature(self) -> float:
        """Legacy climate property for Home Assistant compatibility."""
        return self._runtime.target

    @property
    def fan_modes(self) -> list[str] | None:
        """Mirror source fan modes when supported."""
        climate = self._source_state()
        return climate.attributes.get("fan_modes") if climate else None

    @property
    def fan_mode(self) -> str | None:
        """Mirror the current source fan mode."""
        climate = self._source_state()
        return climate.attributes.get("fan_mode") if climate else None

    @property
    def preset_modes(self) -> list[str] | None:
        """Mirror source presets when supported."""
        climate = self._source_state()
        return climate.attributes.get("preset_modes") if climate else None

    @property
    def preset_mode(self) -> str | None:
        """Mirror the current source preset."""
        climate = self._source_state()
        return climate.attributes.get("preset_mode") if climate else None

    @property
    def swing_modes(self) -> list[str] | None:
        """Mirror source swing modes when supported."""
        climate = self._source_state()
        return climate.attributes.get("swing_modes") if climate else None

    @property
    def swing_mode(self) -> str | None:
        """Mirror the current source swing mode."""
        climate = self._source_state()
        return climate.attributes.get("swing_mode") if climate else None

    @property
    def swing_horizontal_modes(self) -> list[str] | None:
        """Mirror horizontal swing modes when supported."""
        climate = self._source_state()
        return climate.attributes.get("swing_horizontal_modes") if climate else None

    @property
    def swing_horizontal_mode(self) -> str | None:
        """Mirror the current horizontal swing mode."""
        climate = self._source_state()
        return climate.attributes.get("swing_horizontal_mode") if climate else None

    @property
    def hvac_action(self) -> HVACAction | None:
        """Mirror the physical climate's current action when available."""
        climate = self._source_state()
        action = climate.attributes.get("hvac_action") if climate else None
        if action is None:
            return None
        try:
            return HVACAction(action)
        except ValueError:
            return None

    async def async_set_temperature(self, **kwargs) -> None:
        """Update desired temperature; heating logic adjusts only the source."""
        temperature = kwargs.get("temperature")
        if temperature is None:
            return
        self._attr_temperature = float(temperature)
        self._attr_native_target_temperature = float(temperature)
        await async_set_target(self.hass, self.entry, float(temperature))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Pass the selected HVAC mode through to the physical climate."""
        if hvac_mode not in self.hvac_modes:
            return
        await self.hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": self._runtime.climate_entity, "hvac_mode": hvac_mode.value},
            blocking=False,
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Pass the selected fan mode through to the physical climate."""
        await self._async_passthrough("set_fan_mode", {"fan_mode": fan_mode})

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Pass the selected preset through to the physical climate."""
        await self._async_passthrough("set_preset_mode", {"preset_mode": preset_mode})

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Pass the selected swing mode through to the physical climate."""
        await self._async_passthrough("set_swing_mode", {"swing_mode": swing_mode})

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Pass horizontal swing mode through when the source supports it."""
        await self._async_passthrough(
            "set_swing_horizontal_mode",
            {"swing_horizontal_mode": swing_horizontal_mode},
        )

    async def async_turn_on(self) -> None:
        """Pass turn-on through to the physical climate."""
        await self._async_passthrough("turn_on")

    async def async_turn_off(self) -> None:
        """Pass turn-off through to the physical climate."""
        await self._async_passthrough("turn_off")

    async def _async_passthrough(self, service: str, data: dict | None = None) -> None:
        """Forward a climate service to the selected physical entity."""
        await self.hass.services.async_call(
            "climate",
            service,
            {"entity_id": self._runtime.climate_entity, **(data or {})},
            blocking=False,
        )
