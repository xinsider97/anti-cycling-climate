"""Anti-Cycling enable switch."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AntiCyclingRuntime, async_set_enabled, device_info_for_climate


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Anti-Cycling enable switch."""
    async_add_entities([AntiCyclingEnableSwitch(hass, entry)])


class AntiCyclingEnableSwitch(SwitchEntity):
    """Enable or disable Anti-Cycling for one configured climate."""

    _attr_has_entity_name = True
    _attr_name = "Anti-Cycling aktiv"
    _attr_icon = "mdi:autorenew"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        runtime: AntiCyclingRuntime = hass.data[entry.domain][entry.entry_id]
        self._attr_unique_id = f"{entry.entry_id}_enabled"
        self._attr_device_info = device_info_for_climate(
            hass, runtime.climate_entity, entry
        )
        self._attr_is_on = runtime.enabled

    async def async_turn_on(self, **kwargs) -> None:
        """Enable control."""
        self._attr_is_on = True
        await async_set_enabled(self.hass, self.entry, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable control without changing the climate entity."""
        self._attr_is_on = False
        await async_set_enabled(self.hass, self.entry, False)
        self.async_write_ha_state()
