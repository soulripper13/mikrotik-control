"""Button platform for Mikrotik Control integration."""
import logging
from datetime import datetime
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_BACKUP_BEFORE_RISKY_ACTIONS,
    CONF_ENABLE_CONTAINER_CONTROLS,
    CONF_ENABLE_REBOOT_BUTTON,
    CONF_ENABLE_SCRIPT_BUTTONS,
    DEFAULT_BACKUP_BEFORE_RISKY_ACTIONS,
    DEFAULT_ENABLE_CONTAINER_CONTROLS,
    DEFAULT_ENABLE_REBOOT_BUTTON,
    DEFAULT_ENABLE_SCRIPT_BUTTONS,
    DOMAIN,
)
from .entity import MikrotikEntity, safe_key

_LOGGER = logging.getLogger(__name__)


def _enable_by_option(entity):
    """Mark an option-created entity enabled by default."""
    entity._attr_entity_registry_enabled_default = True
    return entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mikrotik buttons."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    enable_reboot_button = entry.options.get(
        CONF_ENABLE_REBOOT_BUTTON,
        DEFAULT_ENABLE_REBOOT_BUTTON,
    )
    enable_script_buttons = entry.options.get(
        CONF_ENABLE_SCRIPT_BUTTONS,
        DEFAULT_ENABLE_SCRIPT_BUTTONS,
    )
    enable_container_controls = entry.options.get(
        CONF_ENABLE_CONTAINER_CONTROLS,
        DEFAULT_ENABLE_CONTAINER_CONTROLS,
    )
    backup_before_risky = entry.options.get(
        CONF_BACKUP_BEFORE_RISKY_ACTIONS,
        DEFAULT_BACKUP_BEFORE_RISKY_ACTIONS,
    )
    entities = []

    # 1. System Reboot button
    if enable_reboot_button:
        entities.append(_enable_by_option(MikrotikRebootButton(coordinator, entry.entry_id, backup_before_risky)))

    # 2. Check Updates button
    entities.append(MikrotikCheckUpdatesButton(coordinator, entry.entry_id))
    entities.append(MikrotikBackupButton(coordinator, entry.entry_id))

    # 3. Dynamic Script buttons
    if enable_script_buttons:
        for script in coordinator.data.get("scripts", []):
            if "name" in script and ".id" in script:
                entities.append(
                    _enable_by_option(
                        MikrotikScriptButton(coordinator, entry.entry_id, script["name"], script[".id"])
                    )
                )

    # 4. Container restart buttons
    if enable_container_controls:
        for container in coordinator.data.get("containers", []):
            if ".id" in container:
                entities.append(
                    _enable_by_option(
                        MikrotikContainerRestartButton(coordinator, entry.entry_id, container[".id"])
                    )
                )

    async_add_entities(entities)


class MikrotikButton(MikrotikEntity, ButtonEntity):
    """Base class for Mikrotik diagnostic buttons."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC


class MikrotikRebootButton(MikrotikButton):
    """Button to reboot the Mikrotik router."""

    _attr_name = "Reboot Router"
    _attr_icon = "mdi:restart"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id, backup_before_risky=False):
        """Initialize reboot button."""
        super().__init__(coordinator, entry_id)
        self.backup_before_risky = backup_before_risky
        self._attr_unique_id = f"{self.device_id}_reboot"

    async def async_press(self) -> None:
        """Press the button to reboot."""
        _LOGGER.warning("Reboot command sent to Mikrotik router: %s", self.host)
        if self.backup_before_risky:
            await self.coordinator.client.create_backup(_backup_name("pre-reboot"))
        await self.coordinator.client.reboot()
        
        # Pause coordinator updates for 60 seconds to allow the router to reboot
        self.coordinator.pause_updates(60)


class MikrotikCheckUpdatesButton(MikrotikButton):
    """Button to check for package updates."""

    _attr_name = "Check for Updates"
    _attr_icon = "mdi:cloud-search"

    def __init__(self, coordinator, entry_id):
        """Initialize check updates button."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{self.device_id}_check_updates"

    async def async_press(self) -> None:
        """Press the button to check for updates."""
        _LOGGER.info("Check updates command sent to Mikrotik router")
        await self.coordinator.client.check_updates()
        await self.coordinator.async_request_refresh()


class MikrotikBackupButton(MikrotikButton):
    """Button to create a RouterOS backup."""

    _attr_name = "Create Backup"
    _attr_icon = "mdi:content-save-cog"

    def __init__(self, coordinator, entry_id):
        """Initialize backup button."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{self.device_id}_create_backup"

    async def async_press(self) -> None:
        """Create a RouterOS backup."""
        await self.coordinator.client.create_backup(_backup_name("manual"))
        await self.coordinator.async_request_refresh()


class MikrotikScriptButton(MikrotikEntity, ButtonEntity):
    """Button representing a Mikrotik script (classified as control/none category)."""

    _device_group = "scripts"
    _attr_icon = "mdi:script-text-outline"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id, script_name, script_id):
        """Initialize script button."""
        super().__init__(coordinator, entry_id)
        self.script_name = script_name
        self.script_id = script_id
        self._attr_name = f"Run Script: {script_name}"
        self._attr_unique_id = f"{self.device_id}_script_{safe_key(script_name)}"

    @property
    def _script_data(self):
        """Get latest script data."""
        for script in self.coordinator.data.get("scripts", []):
            if script.get("name") == self.script_name:
                return script
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return script details."""
        data = self._script_data
        if data:
            return {
                "run_count": data.get("run-count", 0),
                "last_started": data.get("last-started", "never"),
                "comment": data.get("comment", ""),
            }
        return {}

    async def async_press(self) -> None:
        """Press the button to execute script."""
        _LOGGER.info("Executing script %s on Mikrotik router", self.script_name)
        data = self._script_data
        target_id = data[".id"] if data and ".id" in data else self.script_id
        await self.coordinator.client.run_script(target_id)
        await self.coordinator.async_request_refresh()


class MikrotikContainerRestartButton(MikrotikEntity, ButtonEntity):
    """Button to restart a RouterOS container."""

    _device_group = "containers"
    _attr_icon = "mdi:restart"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id, container_id):
        """Initialize restart button."""
        super().__init__(coordinator, entry_id)
        self.container_id = container_id

        container = self._container_data
        name = self._container_name(container)
        self._attr_name = f"Restart Container {name}"
        self._attr_unique_id = f"{self.device_id}_container_{safe_key(container_id)}_restart"

    @staticmethod
    def _container_name(container):
        """Return the best available display name for a container."""
        if not container:
            return "unknown"
        return (
            container.get("comment")
            or container.get("hostname")
            or container.get("name")
            or container.get("remote-image")
            or container.get(".id", "unknown")
        )

    @property
    def _container_data(self):
        """Get latest container data."""
        for container in self.coordinator.data.get("containers", []):
            if container.get(".id") == self.container_id:
                return container
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return container details."""
        data = self._container_data
        if not data:
            return {}

        attrs = {
            "routeros_id": data.get(".id"),
            "status": data.get("status"),
            "image": data.get("remote-image"),
            "hostname": data.get("hostname"),
            "comment": data.get("comment", ""),
            "interface": data.get("interface"),
            "root_dir": data.get("root-dir"),
            "start_on_boot": data.get("start-on-boot"),
        }
        return {key: value for key, value in attrs.items() if value not in (None, "")}

    async def async_press(self) -> None:
        """Restart the container."""
        await self.coordinator.client.restart_container(self.container_id)
        await self.coordinator.async_request_refresh()


def _backup_name(prefix: str) -> str:
    """Return a RouterOS-safe backup name."""
    return f"ha-{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
