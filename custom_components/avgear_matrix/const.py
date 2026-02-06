"""Constants for AVGear Matrix Switcher integration."""

DOMAIN = "avgear_matrix"

# Config keys
CONF_HOST = "host"
CONF_PORT = "port"

# Defaults
DEFAULT_PORT = 4001
DEFAULT_SCAN_INTERVAL = 30

# Options
CONF_SCAN_INTERVAL = "scan_interval"
CONF_OUTPUT_NAMES = "output_names"
CONF_INPUT_NAMES = "input_names"
CONF_PRESET_NAMES = "preset_names"
MAX_NAME_LENGTH = 50

# Device info
ATTR_MODEL = "model"
ATTR_FIRMWARE = "firmware"

# Matrix specs (8x8)
NUM_INPUTS = 8
NUM_OUTPUTS = 8
NUM_PRESETS = 10  # 0-9
