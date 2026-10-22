"""Anti-Cycling Climate integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    CONF_CLIMATE_ENTITY,
    CONF_SENSOR_ENTITY,
    CONF_COOLING_SETBACK,
    CONF_HEAT_OFFSET,
    CONF_TARGET_MAX,
    CONF_TARGET_MIN,
    CONF_TARGET_STEP,
    CONF_TEMPERATURE_UNIT,
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
    target_temp_step: float
    hysteresis_step: float
    temperature_unit: str
    warm_margin: float
    cooling_setback: float
    heat_offset: float
    target: float = DEFAULT_TARGET
    enabled: bool = DEFAULT_ENABLED
    warm_latch: bool = False
    unsubscribe: object | None = None
    virtual_climate: object | None = None


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
        target_temp_step=float(entry.data[CONF_TARGET_STEP]),
        hysteresis_step=_convert_celsius(
            0.5,
            entry.data.get(CONF_TEMPERATURE_UNIT, hass.config.units.temperature_unit),
            delta=True,
        ),
        temperature_unit=entry.data.get(
            CONF_TEMPERATURE_UNIT, hass.config.units.temperature_unit
        ),
        warm_margin=float(entry.options.get(CONF_WARM_MARGIN, entry.data[CONF_WARM_MARGIN])),
        cooling_setback=float(entry.options.get(CONF_COOLING_SETBACK, entry.data[CONF_COOLING_SETBACK])),
        heat_offset=float(entry.options.get(CONF_HEAT_OFFSET, entry.data[CONF_HEAT_OFFSET])),
        target=float(
            entry.options.get(
                "target",
                _convert_celsius(
                    DEFAULT_TARGET,
                    entry.data.get(
                        CONF_TEMPERATURE_UNIT, hass.config.units.temperature_unit
                    ),
                ),
            )
        ),
        enabled=bool(entry.options.get("enabled", DEFAULT_ENABLED)),
    )
    runtime.target = normalize_target(runtime, runtime.target)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime

    # The previous integration version exposed the requested target as a number
    # entity. The virtual climate now owns that control, so remove the obsolete
    # registry entry after preserving its value in config-entry options.
    entity_registry = er.async_get(hass)
    old_target_entity_id = entity_registry.async_get_entity_id(
        "number", DOMAIN, f"{entry.entry_id}_target"
    )
    if old_target_entity_id is not None:
        entity_registry.async_remove(old_target_entity_id)

    @callback
    def _state_changed(event: Event) -> None:
        if runtime.virtual_climate is not None:
            runtime.virtual_climate.async_write_ha_state()
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


def device_info_for_entry(entry: ConfigEntry) -> DeviceInfo:
    """Describe the Anti-Cycling service device for this climate entity."""
    return DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"{entry.title} Anti-Cycling",
    )


def _convert_celsius(value: float, unit: str, *, delta: bool = False) -> float:
    """Convert a Celsius default to the climate entity's unit."""
    if unit == UnitOfTemperature.FAHRENHEIT:
        if delta:
            return value * 9 / 5
        return TemperatureConverter.convert(
            value, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT
        )
    return value


def normalize_target(runtime: AntiCyclingRuntime, target: float) -> float:
    """Clamp and align a requested target to the source climate's step."""
    target = min(max(target, runtime.target_min), runtime.target_max)
    target = runtime.target_min + round(
        (target - runtime.target_min) / runtime.target_temp_step
    ) * runtime.target_temp_step
    return min(max(target, runtime.target_min), runtime.target_max)


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
    """Store the virtual climate's requested temperature."""
    runtime: AntiCyclingRuntime = hass.data[DOMAIN][entry.entry_id]
    target = normalize_target(runtime, target)
    runtime.target = target
    hass.config_entries.async_update_entry(entry, options={**entry.options, "target": target})
    if runtime.virtual_climate is not None:
        runtime.virtual_climate.async_write_ha_state()
    await _async_apply_control(hass, runtime)


async def async_set_enabled(hass: HomeAssistant, entry: ConfigEntry, enabled: bool) -> None:
    """Store enable switch changes as config-entry options."""
    runtime: AntiCyclingRuntime = hass.data[DOMAIN][entry.entry_id]
    runtime.enabled = enabled
    hass.config_entries.async_update_entry(entry, options={**entry.options, "enabled": enabled})
    if runtime.virtual_climate is not None:
        runtime.virtual_climate.async_write_ha_state()
    await _async_apply_control(hass, runtime)


async def _async_apply_control(hass: HomeAssistant, runtime: AntiCyclingRuntime) -> None:
    """Apply the user's anti-cycling rules to a supported climate entity."""
    climate = hass.states.get(runtime.climate_entity)
    if climate is None:
        return
    # The virtual climate mirrors all source modes and controls. Anti-Cycling
    # is an additional heating-only policy; every other mode passes the user's
    # requested target directly through to the physical climate.
    if not runtime.enabled or climate.state != "heat":
        await _async_set_underlying_temperature(hass, runtime, climate, runtime.target)
        return
    sensor = hass.states.get(runtime.sensor_entity)
    if sensor is None:
        return
    try:
        room_temperature = float(sensor.state)
        sensor_unit = sensor.attributes.get("unit_of_measurement", runtime.temperature_unit)
        if sensor_unit != runtime.temperature_unit:
            room_temperature = TemperatureConverter.convert(
                room_temperature, sensor_unit, runtime.temperature_unit
            )
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
            step = runtime.hysteresis_step
            setpoint = (int(current_temperature / step) * step) - runtime.heat_offset
    if setpoint is None:
        return
    await _async_set_underlying_temperature(hass, runtime, climate, setpoint)


async def _async_set_underlying_temperature(
    hass: HomeAssistant,
    runtime: AntiCyclingRuntime,
    climate,
    setpoint: float,
) -> None:
    """Clamp and send a safe setpoint to the real climate entity."""
    old_setpoint = climate.attributes.get("temperature")
    setpoint = min(max(setpoint, runtime.target_min), runtime.target_max)
    increment = runtime.target_temp_step
    setpoint = runtime.target_min + round(
        (setpoint - runtime.target_min) / increment
    ) * increment
    setpoint = min(max(setpoint, runtime.target_min), runtime.target_max)
    try:
        if old_setpoint is not None and abs(float(old_setpoint) - setpoint) < 0.01:
            return
    except (TypeError, ValueError):
        pass
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": runtime.climate_entity, "temperature": round(setpoint, 2)},
        blocking=False,
    )
