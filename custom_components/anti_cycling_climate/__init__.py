"""Anti-Cycling Climate integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_CLIMATE_ENTITY,
    CONF_SENSOR_ENTITY,
    CONF_COOLING_SETBACK,
    CONF_HEAT_OFFSET,
    CONF_TARGET_MAX,
    CONF_TARGET_MIN,
    CONF_TARGET_STEP,
    CONF_WARM_MARGIN,
    DEFAULT_COOLING_SETBACK,
    DEFAULT_HEAT_OFFSET,
    DEFAULT_ENABLED,
    DEFAULT_TARGET,
    DEFAULT_WARM_MARGIN,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class AntiCyclingRuntime:
    """Runtime settings and hysteresis state for one configured room."""

    climate_entity: str
    sensor_entity: str
    target_min: float
    target_max: float
    target_step: float
    target_temp_step: float
    warm_margin: float
    cooling_setback: float
    heat_offset: float
    target: float = DEFAULT_TARGET
    enabled: bool = DEFAULT_ENABLED
    warm_latch: bool = False
    unsubscribe: object | None = None


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration from YAML (not supported)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a configured room."""
    runtime = AntiCyclingRuntime(
        climate_entity=entry.data[CONF_CLIMATE_ENTITY],
        sensor_entity=entry.data[CONF_SENSOR_ENTITY],
        target_min=float(entry.data[CONF_TARGET_MIN]),
        target_max=float(entry.data[CONF_TARGET_MAX]),
        target_step=float(entry.data[CONF_TARGET_STEP]),
        target_temp_step=float(entry.data[CONF_TARGET_STEP]),
        warm_margin=float(entry.options.get(CONF_WARM_MARGIN, entry.data[CONF_WARM_MARGIN])),
        cooling_setback=float(entry.options.get(CONF_COOLING_SETBACK, entry.data[CONF_COOLING_SETBACK])),
        heat_offset=float(entry.options.get(CONF_HEAT_OFFSET, entry.data[CONF_HEAT_OFFSET])),
        target=float(entry.options.get("target", DEFAULT_TARGET)),
        enabled=bool(entry.options.get("enabled", DEFAULT_ENABLED)),
    )
    runtime.target = min(max(runtime.target, runtime.target_min), runtime.target_max)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime

    @callback
    def _state_changed(event: Event) -> None:
        hass.async_create_task(_async_apply_control(hass, runtime))

    runtime.unsubscribe = async_track_state_change_event(
        hass,
        [runtime.climate_entity, runtime.sensor_entity],
        _state_changed,
    )
    entry.async_on_unload(runtime.unsubscribe)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    hass.async_create_task(_async_apply_control(hass, runtime))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a room config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True


def device_info_for_climate(
    hass: HomeAssistant, climate_entity_id: str, entry: ConfigEntry
) -> DeviceInfo:
    """Attach controls to the selected climate's existing device when available."""
    entity_registry = er.async_get(hass)
    climate_entity = entity_registry.async_get(climate_entity_id)
    if climate_entity is not None and climate_entity.device_id is not None:
        device = dr.async_get(hass).async_get(climate_entity.device_id)
        if device is not None and device.identifiers:
            return DeviceInfo(
                identifiers=set(device.identifiers),
                name=device.name,
                manufacturer=device.manufacturer,
                model=device.model,
            )
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
    )


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when hysteresis settings change in the options flow."""
    runtime: AntiCyclingRuntime | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if runtime is None:
        return
    if (
        runtime.warm_margin != float(entry.options.get(CONF_WARM_MARGIN, runtime.warm_margin))
        or runtime.cooling_setback != float(entry.options.get(CONF_COOLING_SETBACK, runtime.cooling_setback))
        or runtime.heat_offset != float(entry.options.get(CONF_HEAT_OFFSET, runtime.heat_offset))
    ):
        await hass.config_entries.async_reload(entry.entry_id)


async def async_set_target(hass: HomeAssistant, entry: ConfigEntry, target: float) -> None:
    """Store target slider changes as config-entry options."""
    runtime: AntiCyclingRuntime = hass.data[DOMAIN][entry.entry_id]
    runtime.target = target
    hass.config_entries.async_update_entry(entry, options={**entry.options, "target": target})
    await _async_apply_control(hass, runtime)


async def async_set_enabled(hass: HomeAssistant, entry: ConfigEntry, enabled: bool) -> None:
    """Store enable switch changes as config-entry options."""
    runtime: AntiCyclingRuntime = hass.data[DOMAIN][entry.entry_id]
    runtime.enabled = enabled
    hass.config_entries.async_update_entry(entry, options={**entry.options, "enabled": enabled})
    if enabled:
        await _async_apply_control(hass, runtime)


async def _async_apply_control(hass: HomeAssistant, runtime: AntiCyclingRuntime) -> None:
    """Apply the user's anti-cycling rules to a supported climate entity."""
    if not runtime.enabled:
        return
    climate = hass.states.get(runtime.climate_entity)
    sensor = hass.states.get(runtime.sensor_entity)
    if climate is None or sensor is None:
        return
    try:
        room_temperature = float(sensor.state)
        current_temperature = float(climate.attributes["current_temperature"])
    except (KeyError, TypeError, ValueError):
        _LOGGER.debug("Temperature unavailable for %s", runtime.climate_entity)
        return

    mode = climate.state
    setpoint: float | None = None
    if mode == "heat":
        if room_temperature <= runtime.target:
            runtime.warm_latch = False
            setpoint = current_temperature
        elif room_temperature >= runtime.target + runtime.warm_margin:
            runtime.warm_latch = True
            setpoint = runtime.cooling_setback
        elif not runtime.warm_latch:
            setpoint = (int(current_temperature * 2) / 2) - runtime.heat_offset
    elif mode in ("cool", "dry"):
        setpoint = runtime.target if current_temperature >= runtime.target else current_temperature

    if setpoint is None:
        return
    old_setpoint = climate.attributes.get("temperature")
    try:
        if old_setpoint is not None and abs(float(old_setpoint) - setpoint) < 0.01:
            return
    except (TypeError, ValueError):
        pass
    setpoint = min(max(setpoint, runtime.target_min), runtime.target_max)
    increment = runtime.target_temp_step
    setpoint = runtime.target_min + round(
        (setpoint - runtime.target_min) / increment
    ) * increment
    setpoint = min(max(setpoint, runtime.target_min), runtime.target_max)
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": runtime.climate_entity, "temperature": round(setpoint, 2)},
        blocking=False,
    )
