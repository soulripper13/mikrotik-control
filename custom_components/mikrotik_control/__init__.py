"""The Mikrotik Control integration."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_ENABLE_CONFIG_AUDIT,
    CONF_ENABLE_CONTAINER_CONTROLS,
    CONF_ENABLE_FIREWALL_CONTROLS,
    CONF_ENABLE_FIREWALL_PROFILES,
    CONF_ENABLE_HEALTH_SCORE,
    CONF_ENABLE_INTERFACE_CONTROLS,
    CONF_ENABLE_INTERFACE_DETAILS,
    CONF_ENABLE_NETWATCH,
    CONF_ENABLE_REBOOT_BUTTON,
    CONF_ENABLE_SCRIPT_BUTTONS,
    CONF_ENABLE_WIREGUARD,
    DEFAULT_ENABLE_CONFIG_AUDIT,
    CONF_USE_SSL,
    CONF_VERIFY_SSL,
    DEFAULT_ENABLE_CONTAINER_CONTROLS,
    DEFAULT_ENABLE_FIREWALL_CONTROLS,
    DEFAULT_ENABLE_FIREWALL_PROFILES,
    DEFAULT_ENABLE_HEALTH_SCORE,
    DEFAULT_ENABLE_INTERFACE_CONTROLS,
    DEFAULT_ENABLE_INTERFACE_DETAILS,
    DEFAULT_ENABLE_NETWATCH,
    DEFAULT_ENABLE_REBOOT_BUTTON,
    DEFAULT_ENABLE_SCRIPT_BUTTONS,
    DEFAULT_ENABLE_WIREGUARD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import MikrotikDataUpdateCoordinator
from .mikrotik_client import MikrotikClient

_LOGGER = logging.getLogger(__name__)

ENTITY_GROUPS = {
    CONF_ENABLE_INTERFACE_DETAILS: (
        ("sensor.", "_interface_"),
    ),
    CONF_ENABLE_INTERFACE_CONTROLS: (
        ("switch.", "_interface_"),
    ),
    CONF_ENABLE_FIREWALL_CONTROLS: (
        ("switch.", "_nat_"),
        ("switch.", "_filter_"),
        ("switch.", "_mangle_"),
    ),
    CONF_ENABLE_FIREWALL_PROFILES: (
        ("switch.", "_firewall_profile_"),
    ),
    CONF_ENABLE_SCRIPT_BUTTONS: (
        ("button.", "_run_script_"),
    ),
    CONF_ENABLE_CONTAINER_CONTROLS: (
        ("switch.", "_containers_container_"),
        ("button.", "_containers_restart_container_"),
    ),
    CONF_ENABLE_REBOOT_BUTTON: (
        ("button.", "_reboot_router"),
    ),
    CONF_ENABLE_WIREGUARD: (
        ("switch.", "_wireguard_peer_"),
        ("sensor.", "_wireguard_peer_"),
        ("binary_sensor.", "_wireguard_peer_"),
    ),
    CONF_ENABLE_NETWATCH: (
        ("binary_sensor.", "_netwatch_"),
    ),
    CONF_ENABLE_HEALTH_SCORE: (
        ("sensor.", "_router_health"),
    ),
    CONF_ENABLE_CONFIG_AUDIT: (
        ("sensor.", "_config_audit"),
    ),
}

ENTITY_GROUP_DEFAULTS = {
    CONF_ENABLE_INTERFACE_DETAILS: DEFAULT_ENABLE_INTERFACE_DETAILS,
    CONF_ENABLE_INTERFACE_CONTROLS: DEFAULT_ENABLE_INTERFACE_CONTROLS,
    CONF_ENABLE_FIREWALL_CONTROLS: DEFAULT_ENABLE_FIREWALL_CONTROLS,
    CONF_ENABLE_FIREWALL_PROFILES: DEFAULT_ENABLE_FIREWALL_PROFILES,
    CONF_ENABLE_SCRIPT_BUTTONS: DEFAULT_ENABLE_SCRIPT_BUTTONS,
    CONF_ENABLE_CONTAINER_CONTROLS: DEFAULT_ENABLE_CONTAINER_CONTROLS,
    CONF_ENABLE_REBOOT_BUTTON: DEFAULT_ENABLE_REBOOT_BUTTON,
    CONF_ENABLE_WIREGUARD: DEFAULT_ENABLE_WIREGUARD,
    CONF_ENABLE_NETWATCH: DEFAULT_ENABLE_NETWATCH,
    CONF_ENABLE_HEALTH_SCORE: DEFAULT_ENABLE_HEALTH_SCORE,
    CONF_ENABLE_CONFIG_AUDIT: DEFAULT_ENABLE_CONFIG_AUDIT,
}


async def _async_sync_entity_group_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Enable or disable existing registry entries to match group options."""
    registry = er.async_get(hass)
    changes = 0

    for option, patterns in ENTITY_GROUPS.items():
        enabled = entry.options.get(option, ENTITY_GROUP_DEFAULTS[option])
        desired_disabled_by = None if enabled else er.RegistryEntryDisabler.INTEGRATION

        for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
            entity_id = registry_entry.entity_id
            if not any(
                entity_id.startswith(prefix) and marker in entity_id
                for prefix, marker in patterns
            ):
                continue

            if registry_entry.disabled_by == desired_disabled_by:
                continue

            registry.async_update_entity(
                entity_id,
                disabled_by=desired_disabled_by,
            )
            changes += 1

    if changes:
        _LOGGER.info("Updated %s Mikrotik entity registry entries from group options", changes)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mikrotik Control from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create client
    client = MikrotikClient(
        hass=hass,
        host=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        port=entry.data[CONF_PORT],
        use_ssl=entry.data.get(CONF_USE_SSL, False),
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, False),
    )

    # Get scan interval
    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)

    # Create coordinator
    coordinator = MikrotikDataUpdateCoordinator(hass, client, scan_interval)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Save reference
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await _async_sync_entity_group_options(hass, entry)

    # Add options listener
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        client: MikrotikClient = data["client"]
        await client.disconnect()

    return unload_ok

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
    await _async_sync_entity_group_options(hass, entry)
