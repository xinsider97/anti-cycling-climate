"""Constants for Anti-Cycling Climate."""

DOMAIN = "anti_cycling_climate"
PLATFORMS = ["number", "switch"]

CONF_CLIMATE_ENTITY = "climate_entity"
CONF_SENSOR_ENTITY = "sensor_entity"
CONF_TARGET_MIN = "target_min"
CONF_TARGET_MAX = "target_max"
CONF_TARGET_STEP = "target_step"
CONF_WARM_MARGIN = "warm_margin"
CONF_COOLING_SETBACK = "cooling_setback"
CONF_HEAT_OFFSET = "heat_offset"

DEFAULT_TARGET = 22.0
DEFAULT_TARGET_MIN = 16.0
DEFAULT_TARGET_MAX = 30.0
DEFAULT_TARGET_STEP = 0.5
DEFAULT_ENABLED = True
DEFAULT_WARM_MARGIN = 1.2
DEFAULT_COOLING_SETBACK = 17.0
DEFAULT_HEAT_OFFSET = 2.0

ATTR_TARGET = "target_temperature"
ATTR_ENABLED = "anti_cycling_enabled"
