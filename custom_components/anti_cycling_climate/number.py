"""Target temperature slider."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AntiCyclingRuntime, async_set_target, device_info_for_entry
from .const import DEFAULT_TARGET


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the target temperature control."""
    async_add_entities([AntiCyclingTargetNumber(hass, entry)])


class AntiCyclingTargetNumber(NumberEntity):
    """A per-room target-temperature slider."""

    _attr_has_entity_name = True
    _attr_name = "Solltemperatur"
    _attr_native_unit_of_measurement = "°C"
    _attr_mode = NumberMode.SLIDER

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        runtime: AntiCyclingRuntime = hass.data[entry.domain][entry.entry_id]
        self._attr_unique_id = f"{entry.entry_id}_target"
        self._attr_device_info = device_info_for_entry(entry)
        self._attr_native_min_value = runtime.target_min
        self._attr_native_max_value = runtime.target_max
        self._attr_native_step = runtime.target_step
        self._attr_native_value = min(
            max(runtime.target or DEFAULT_TARGET, runtime.target_min), runtime.target_max
        )

    async def async_set_native_value(self, value: float) -> None:
        """Update target and immediately recalculate control output."""
        self._attr_native_value = value
        await async_set_target(self.hass, self.entry, value)
        self.async_write_ha_state()
