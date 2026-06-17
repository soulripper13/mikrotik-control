"""Constants for the Mikrotik Control integration."""
from homeassistant.const import Platform

DOMAIN = "mikrotik_control"

# Configuration keys
CONF_USE_SSL = "use_ssl"
CONF_VERIFY_SSL = "verify_ssl"
CONF_ENABLE_INTERFACE_DETAILS = "enable_interface_details"
CONF_ENABLE_INTERFACE_CONTROLS = "enable_interface_controls"
CONF_ENABLE_FIREWALL_CONTROLS = "enable_firewall_controls"
CONF_ENABLE_SCRIPT_BUTTONS = "enable_script_buttons"
CONF_ENABLE_CONTAINER_CONTROLS = "enable_container_controls"
CONF_ENABLE_REBOOT_BUTTON = "enable_reboot_button"

# Defaults
DEFAULT_PORT = 8728
DEFAULT_PORT_SSL = 8729
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_ENABLE_INTERFACE_DETAILS = False
DEFAULT_ENABLE_INTERFACE_CONTROLS = False
DEFAULT_ENABLE_FIREWALL_CONTROLS = False
DEFAULT_ENABLE_SCRIPT_BUTTONS = False
DEFAULT_ENABLE_CONTAINER_CONTROLS = True
DEFAULT_ENABLE_REBOOT_BUTTON = False

# Platforms
PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
]

# Service Names / Attributes
ATTR_SCRIPT_NAME = "script_name"
SERVICE_RUN_SCRIPT = "run_script"
