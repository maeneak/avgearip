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

# Device info
ATTR_MODEL = "model"
ATTR_FIRMWARE = "firmware"

# Matrix specs (8x8)
NUM_INPUTS = 8
NUM_OUTPUTS = 8
NUM_PRESETS = 10  # 0-9

# Input options for select entities
INPUT_OPTIONS = [f"Input {i}" for i in range(1, NUM_INPUTS + 1)] + ["Off"]
