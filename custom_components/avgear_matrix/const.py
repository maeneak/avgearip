"""Constants for AVGear Matrix Switcher integration."""

DOMAIN = "avgear_matrix"

# Config keys
CONF_HOST = "host"
CONF_PORT = "port"
CONF_DEVICE_UID = "device_uid"

# Defaults
DEFAULT_PORT = 4001
DEFAULT_SCAN_INTERVAL = 30

# Options
CONF_SCAN_INTERVAL = "scan_interval"
CONF_INPUT_NAMES = "input_names"
CONF_PRESET_NAMES = "preset_names"
CONF_NUM_INPUTS = "num_inputs"
CONF_NUM_OUTPUTS = "num_outputs"
MAX_NAME_LENGTH = 50

# Device info
ATTR_MODEL = "model"
ATTR_FIRMWARE = "firmware"

# Matrix specs (8x8)
NUM_INPUTS = 8
NUM_OUTPUTS = 8
NUM_PRESETS = 10  # 0-9

# EDID built-in slot labels (for the EDID/x/y. command). The device's own
# firmware-embedded profiles; returned dumps may not differentiate slots on
# all firmware revisions, so the select entity treats these as write-only
# labels the user can round-robin through.
EDID_PROFILES: dict[int, str] = {
    1: "1080p 2D 2CH",
    2: "1080p 3D 2CH",
    3: "1080p 2D Multichannel",
    4: "1080p 3D Multichannel",
    5: "4K 30Hz 2D",
    6: "4K 60Hz 2D",
}
